# yoloimporter
import directly from PyPI

YOLO Importer is for those that like to live dangerously. For those that don't have
time to manage a local, reproducible, isolated, Python environment but instead
need their libraries NOW!

YOLO Importer will resolve missing dependencies from the internet, and make them
immediately available to the current Python session, all through the import
system. When the current Python session is ended, these dependencies disappear,
leaving no trace of their use.

## Usage

```python
import yoloimporter.doit

# these do not need to be already-installed
# this will work in any environment that has yoloimporter installed
import requests
from rich import markdown
from rich import console

out = console.Console()
this_page = requests.get('https://raw.githubusercontent.com/ucodery/yoloimporter/master/README.md')
out.print(markdown.Markdown(''.join(this_page.text)))
```

## Installation

YOLO Importer still needs to be installed before use, but nothing else you need will!
Try installing the latest version from pypi.org

```bash
python -m pip install yoloimporter
```
