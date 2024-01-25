from importlib.abc import MetaPathFinder, Loader
from importlib.util import spec_from_loader
import importlib.machinery
from collections import namedtuple
import os.path
import subprocess
import sys
import re
from urllib.request import urlopen
from tempfile import NamedTemporaryFile
from zipimport import zipimporter
from zipfile import ZipFile

__version__ = '0.1'

# TODO: strategies
# in-memory whl - disappear after exit
# full install - import becomes part of environment


class ResolveError(Exception):
    """Was not able to fulfill a new package addition to the current environment"""


class _PyPI_Finder:
    package_url = re.compile(
        r"""link\ 
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
        """,
        re.VERBOSE,
    )

    info = namedtuple('info', ['project_name', 'version', 'url', 'source'])
    # Any package part of a prior resolve will influence future resolves
    resolved_packages = {}

    @staticmethod
    def normalize_project_name(name):
        return name.lower()

    @classmethod
    def _remove_resolved(cls, package):
        this_project = cls.resolved_packages.pop(package, None)
        if this_project:
            for mod, project in cls.resolved_packages.items():
                if project.project_name == this_project.project_name:
                    cls.resolved_packages.pop(mod)

    @classmethod
    def find(cls, package, use_cache=True):
        pre_cache = cls.resolved_packages.copy()
        try:
            if use_cache is False:
                cls._remove_resolved(package)
            if package not in cls.resolved_packages:
                cls._pip_resolve(package)
            return cls.resolved_packages[package]
        except ResolveError:
            cls.resolved_packages = pre_cache

    @classmethod
    def _pip_resolve(cls, package):
        with NamedTemporaryFile(delete_on_close=False) as temp_constraints:
            temp_constraints.write(
                '\n'.join(
                    f'{p.project_name}=={p.version}'
                    for p in cls.resolved_packages.values()
                ).encode('utf-8')
            )
            temp_constraints.close()
            solve = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'pip',
                    'install',
                    '--only-binary',
                    ':all:',
                    '--no-cache-dir',
                    '--dry-run',
                    '-vv',
                    '--no-color',
                    '--progress-bar',
                    'off',
                    '-c',
                    temp_constraints.name,
                    package,
                ],
                text=True,
                capture_output=True,
            )
        if solve.returncode != 0:
            raise ResolveError('pip errored out')

        found_projects = {}
        resolved_projects = set()
        for line in solve.stdout.splitlines():
            found = re.search(cls.package_url, line)
            if found:
                found_projects[
                    cls.normalize_project_name(found.group('project'))
                ] = cls.info(
                    found.group('project'),
                    found.group('version'),
                    found.group('url'),
                    None,
                )
            _, _check, would_install = line.partition('Would install ')
            if would_install:
                resolved_projects = {
                    cls.normalize_project_name(a.rsplit('-', 1)[0])
                    for a in would_install.split(' ')
                }
                break  # early as rest of stdout is not about solve
        if not resolved_projects:
            raise ResolveError('could not find any package to resolve')

        for resolved in resolved_projects:
            if resolved not in found_projects:
                raise ResolveError(
                    'could not find resolved information for required package'
                )
            project = found_projects[resolved]
            project = project._replace(source=cls.download(project))
            for mod in cls.index_modules(project):
                exists = cls.resolved_packages.get(mod, None)
                if exists:
                    if (
                        project.project_name == exists.project_name
                        and project.version == exists.version
                    ):
                        break  # move on to next project
                    raise ResolveError(
                        'fulfilling this import request would introduce version conflicts'
                    )
                cls.resolved_packages[mod] = project

    @classmethod
    def download(cls, project):
        # this should be the responsibility of the Loader,
        # but for now using zipimporter that needs real files
        pypi_request = urlopen(project.url)
        if pypi_request.code != 200:
            raise ResolveError('failed to retrieve distribution')
        with NamedTemporaryFile(delete=False, suffix='.zip') as temp_source:
            temp_source.write(pypi_request.read())
        return temp_source.name

    @classmethod
    def index_modules(cls, project):
        top_level_modules = set()
        for name in ZipFile(project.source).namelist():
            mod_name, mod_type = os.path.splitext(name)
            mod = mod_name.removesuffix('/__init__')
            if mod_type in importlib.machinery.all_suffixes() and mod.isidentifier():
                top_level_modules.add(mod)
        return top_level_modules


def include(project):
    """Locate a version of project from PyPI that will resolve into the current environment

    This allows fetching of projects that don't match their package name (beautifulsoup4/ bs4)
    and is not needed when the project and package names normalize equivalently

    After pre-fetching with this function, the actual package can be imported as usual
    """
    pre_cache = _PyPI_Finder.resolved_packages.copy()
    try:
        _PyPI_Finder._pip_resolve(project)
        return True
    except ResolveError:
        return False


class YOLOFinder(MetaPathFinder, Loader):
    def find_spec(self, fullname, path=None, target=None):
        if path:
            # not responsible for finding sub-modules
            return None
        try:
            # for reload (target provided) re-search pypi
            project = _PyPI_Finder.find(fullname, use_cache=(target is None))
            spec = spec_from_loader(
                fullname, zipimporter(project.source), origin=project.url
            )
            spec.submodule_search_locations = [project.source + '/' + fullname]
            return spec
        except Exception:
            return None
