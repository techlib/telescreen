Name:           telescreen
Version:        0.1.0
Release:        1%{?dist}
Summary:        Digital signage player for GNOME

Group:          Applications/Multimedia
License:        MIT
URL:            https://github.com/techlib/telescreen

BuildRoot:      %(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)
BuildArch:      noarch

Source0:        %{name}-%{version}.tar.gz

Requires:       python3, python3-libcec
Requires:       python3-twisted, python3-simplejson, python3-jsonschema
Requires:       python3-PyYAML, python3-gstreamer1, python3-gobject
Requires:       gobject-introspection, gtk3, webkitgtk4, gdk-pixbuf2
Requires:       clutter, clutter-gst3, gstreamer1, libcec

%define debug_package %{nil}

%description
This software aims to greatly simplify management of digital information
screens in libraries and similar institutions. Its development has been
funded by NTK and VISK.

%prep
%setup -q -n %{name}-%{version}

%build
%{__python3} setup.py build

%install
%{__python3} setup.py install -O1 --skip-build --root %{buildroot}

%check
%{__python} setup.py test

%clean
rm -rf %{buildroot}


%files
%defattr(644,root,root,755)
%doc LICENSE.md README.md
%{python3_sitelib}/*

%attr(755,root,root) %{_bindir}/*


%changelog
* Mon Dec 19 2016 Jan Dvořák <jan.dvorak@techlib.cz> - 0.1.0-1
- Initial release
