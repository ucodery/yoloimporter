# yoloimport
import directly from PyPI

YOLO Import is for those that like to live dangerously. For those that don't have
time to manage a local, reproducible, isolated, Python environment but instead
need their libraries NOW!

YOLO Import will resolve missing dependencies from the internet, and make them
immediately available to the current Python session, all through the import
system. When the current Python session is ended, these dependencies disappear,
leaving no trace of their use.

## Usage

```python
import yoloimport.doit

# these do not need to be already-installed
# this will work in any environment that has yoloimport installed
import requests
from rich import markdown
from rich import console

out = console.Console()
this_page = requests.get('https://raw.githubusercontent.com/ucodery/yoloimport/master/README.md')
out.print(markdown.Markdown(''.join(this_page.text)))
```

## Installation

YOLO Import still needs to be installed before use, but nothing else you need will!
Try installing the latest version from pypi.org

```bash
python -m pip install yoloimport
```
