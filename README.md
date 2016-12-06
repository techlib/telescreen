# NTK Telescreen

This software aims to greatly simplify management of digital information screens in libraries and similar institutions. Its development has been funded by [NTK][] and [VISK][].

[NTK]: http://techlib.cz/
[VISK]: http://visk.nkp.cz/

This software need repository from:
* https://unitedrpms.github.io/
* https://github.com/UnitedRPMs/unitedrpms.github.io/blob/master/README.md

Tested with software depenedency:
```
    dnf install gstreamer{1,}-{ffmpeg,libav,plugins-{good,ugly,bad{,-free,-nonfree}}} --setopt=strict=0
    dnf install clutter-gst3 libcec python3-gstreamer1
```
Python dependency:
```
pip install twisted zmq txzmq pyyaml jsonschema
```
python3 setup.py bdist_rpm

