from importlib.abc import MetaPathFinder, Loader
from importlib.machinery import ModuleSpec
from importlib.util import spec_from_loader
from collections import namedtuple
import subprocess
import sys
import re
from urllib.request import urlopen
from tempfile import NamedTemporaryFile
from io import BytesIO
from zipimport import zipimporter

__version__ = "0.0"

# TODO: strategies
# in-memory whl - disappear after exit
# full install - import becomes part of environment


class _PyPI_Finder:

    package_url = re.compile(r'''link\ 
    (?P<url>
     https://files\.pythonhosted\.org/packages/  # this is where pypi.org stores wheels
     [0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{60}/       # hash-buckets
     (?P<package>.+?)                            # the package name is the start of final path component
     -[^-]+-[^-]+-[^-]+-[^-]+\.whl               # wheel names always have 5 parts separated by '-' and end in .whl
    )\ 
    \(from\ https://pypi.org/simple/             # the pypi url that linked to pythonhosted
    (?P<project>[^/]+)/\)                        # project name is the entire final component
    (?:\ \([^)]*\))?,\                           # if the distribution has install conditions they are mentioned here
    version:\ (?P<version>[0-9.]+)               # the version of this distribution
    ''', re.VERBOSE)

    info = namedtuple('info', ['package_name', 'version', 'url'])
    # Any package part of a prior resolve will influence future resolves
    resolved_packages = {}

    @staticmethod
    def normalize_project_name(name):
        return name.lower()

    @classmethod
    def find(cls, package, use_cache=True):
        if use_cache is False:
            cls.resolved_packages.pop(package, None)
        if package not in cls.resolved_packages:
            cls._pip_resolve(package)
        project = cls.resolved_packages.get(package, None)
        return project.url if project else None

    @classmethod
    def _pip_resolve(cls, package):
        with NamedTemporaryFile(delete_on_close=False) as temp_constraints:
            temp_constraints.write("\n".join(f"{p.package_name}=={p.version}" for p in cls.resolved_packages.values()).encode("utf-8"))
            temp_constraints.close()
            solve = subprocess.run([sys.executable, "-m", "pip", "install", "--only-binary", ":all:", "--no-cache-dir", "--dry-run", "-vv", "--no-color", "--progress-bar", "off", "-c", temp_constraints.name, package], text= True, capture_output=True)
        if solve.returncode != 0:
            return

        found_projects = {}
        resolved_projects = set()
        for line in solve.stdout.splitlines():
            found = re.search(cls.package_url, line)
            if found:
                found_projects[found.group('project')] = cls.info(found.group('package'), found.group('version'), found.group('url'))
            _, _check, would_install = line.partition("Would install ")
            if would_install:
                resolved_projects = {cls.normalize_project_name(a.rsplit("-", 1)[0]) for a in would_install.split(" ")}
                break # early as rest of stdout is not about solve

        if not resolved_projects:
            return
        resolved_packages = {}
        for resolved in resolved_projects:
            # cannot proceed if urls were not found for some projects that pip says need to be installed
            if resolved not in found_projects:
                return
            project = found_projects[resolved]
            if project.package_name in cls.resolved_packages:
                # cannot proceed if fulfilling this import request would introduce version conflicts
                if project.version != cls.resolved_packages[project.package_name].version:
                    return
                continue
            resolved_packages[project.package_name] = project

        # don't update global cache unless this entire resolve works with the current environment
        cls.resolved_packages.update(resolved_packages)

    @classmethod
    def download(cls, url):
        # this should be the responsibility of the Loader,
        # but for now using zipimporter that needs real files
        pypi_request = urlopen(url)
        if pypi_request.code != 200:
            return None
        with NamedTemporaryFile(delete=False, suffix='.zip') as temp_source:
            temp_source.write(pypi_request.read())
            return temp_source.name


class YOLOFinder(MetaPathFinder, Loader):

    def find_spec(self, fullname, path=None, target=None):
        if path:
            # not responsible for finding sub-modules
            return None
        try:
            # for reload (target provided) re-search pypi
            project = _PyPI_Finder.find(fullname, use_cache=(target is None))
            if project is None:
                return None
            temp_source = _PyPI_Finder.download(project)
            if temp_source is None:
                return None
            spec = spec_from_loader(fullname, zipimporter(temp_source), origin=project)
            spec.submodule_search_locations = [temp_source+'/'+fullname]
            return spec
        except Exception as e:
            return None


sys.meta_path.append(YOLOFinder())
