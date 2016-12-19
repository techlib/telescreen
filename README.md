# NTK Telescreen

This software aims to greatly simplify management of digital information screens in libraries and similar institutions. Its development has been funded by [NTK][] and [VISK][].

[NTK]: http://techlib.cz/
[VISK]: http://visk.nkp.cz/

## Development

We are assuming that your development environment is a current release of Fedora.

First, add the [UnitedRPMs](https://github.com/UnitedRPMs/unitedrpms.github.io) repository to your system, then install some codecs and libraries:

```bash
dnf install -y --exclude '*-devel' --exclude '*-debug' \
               'gstreamer1-plugins-*' gstreamer1-libav
dnf install -y gobject-introspection-devel gtk3-devel webkitgtk4-devel \
               gdk-pixbuf2-devel clutter-devel clutter-gst3-devel \
               gstreamer1-devel libcec
```

The development packages are required for their GObject introspection `.gir` files.

As for the required Python modules, install them using the package manager:

```bash
dnf install -y python3-{twisted,simplejson,jsonschema,PyYAML,gstreamer1,gobject,txzmq}
```
