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
Python dependency is specified in requirements.txt. Bud project internaly need python GObject repository for gst, clutter, gtk3 and GDK, webkit2gtk

python3 setup.py bdist_rpm

GStreamer is used as playback device and can play stream video/image from URI sended by indoktrinator
