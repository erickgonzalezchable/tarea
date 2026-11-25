#!/bin/sh
cd "$(dirname "$0")" || exit 1
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "Falta Tkinter. Instálalo según tu distribución:"
    echo "  Debian/Ubuntu/Mint:  sudo apt install python3-tk"
    echo "  Fedora:              sudo dnf install python3-tkinter"
    echo "  Arch/Manjaro:        sudo pacman -S tk"
    echo "  openSUSE:            sudo zypper install python3-tk"
    exit 1
fi
exec python3 -m app.main
