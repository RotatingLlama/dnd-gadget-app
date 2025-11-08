Purpose
-------
Files that are compiled should be moved out of the App tree and placed here.  They are then replaced in the App tree with their compiled `.mpy` versions.

Use
---
```
[pip install --upgrade mpy-cross]
[git] mv ../App/xyz/file.py ./
mpy-cross -march=armv6m file.py
[git] mv file.mpy ../App/xyz/
```
