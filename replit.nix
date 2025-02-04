
{ pkgs }: {
  deps = [
    pkgs.lsof
    pkgs.tk
    pkgs.tcl
    pkgs.qhull
    pkgs.pkg-config
    pkgs.gtk3
    pkgs.gobject-introspection
    pkgs.ghostscript
    pkgs.freetype
    pkgs.ffmpeg-full
    pkgs.cairo
    pkgs.python312Packages.pyngrok
    # Chrome dependencies
    pkgs.chromium
    pkgs.glib
    pkgs.nss
    pkgs.nspr
    pkgs.at-spi2-atk
    pkgs.cups
    pkgs.dbus
    pkgs.expat
    pkgs.libdrm
    pkgs.mesa
  ];
}
