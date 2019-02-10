# Houdini_Image_Browser

A Python Panel featuring a thumbnail database with automatic thumbnail generation, large image previewer and interaction with Houdini Nodes.

![alt text](res/preview.png)

## Installation

* Download and extract the repository into $HOME/houdini17.0/scripts/python
* Move HoudiniImageBrowser.pypanel from /_install to $HOME/houdini17.0/python_panels
* Install imagemagick for your system following the instructions here: http://docs.wand-py.org/en/0.5.0/guide/install.html#install-imagemagick-on-windows
* Install the python dependencies by running `pip install --target=%USERPROFILE%\Documents\houdini17.0\python2.7libs -r requirements.txt` from within the /_install directory. This needs a system install of Python27.

## Usage

* Browse your system via the tree view or text bar. Image thumbnails are generated on the fly for a wide range of formats including EXR and HDR.
* You can alter the thumnbail size with the Thumbnail menu
* You can also use this menu to generate thumnbails for a directory of textures or HDRIs recursively - i.e without needing to navigate through each subfolder. This process can be slow for a large image collection.
* Use the GOTO menu to save directories for quick navigation or set a default path for the panel to load at startup
* Click a thumnbail for a large preview. Double-click to send this image path to a selected node (e.g a Texture)

## Info

* The browser 