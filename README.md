# NTK Telescreen

This software aims to greatly simplify management of digital information screens in libraries and similar institutions.


## Development

We are assuming that your development environment is a current release of Fedora.

```bash
dnf install -y --exclude '*-devel*' --exclude '*-debug' \
               'gstreamer1-plugins-*' gstreamer1-libav
dnf install -y gobject-introspection gtk3 webkitgtk4 gdk-pixbuf2 clutter \
               clutter-gst3 gstreamer1 libcec
```

As for the required Python modules, install them using the package manager:

```bash
dnf install -y python3-{twisted,simplejson,jsonschema,PyYAML,gstreamer1} \
               python3-{gobject,zmq,zope-interface,libcec}
```
