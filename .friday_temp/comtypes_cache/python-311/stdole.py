from enum import IntFlag

import comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 as __wrapper_module__
from comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 import (
    IFont, OLE_XSIZE_HIMETRIC, OLE_YSIZE_PIXELS, _lcid, IPictureDisp,
    HRESULT, typelib_path, FONTNAME, FONTUNDERSCORE, IDispatch,
    Default, FONTSIZE, OLE_XPOS_CONTAINER, COMMETHOD, IFontEventsDisp,
    dispid, OLE_ENABLEDEFAULTBOOL, IPicture, VgaColor, Library,
    StdFont, OLE_XSIZE_CONTAINER, BSTR, StdPicture, Unchecked,
    OLE_HANDLE, OLE_CANCELBOOL, VARIANT_BOOL, DISPMETHOD, IFontDisp,
    Checked, OLE_COLOR, FontEvents, OLE_YPOS_HIMETRIC, Color,
    DISPPROPERTY, Picture, Font, FONTBOLD, EXCEPINFO,
    OLE_XSIZE_PIXELS, Monochrome, DISPPARAMS, OLE_YPOS_PIXELS,
    IEnumVARIANT, _check_version, OLE_YSIZE_HIMETRIC, Gray, GUID,
    CoClass, IUnknown, OLE_XPOS_HIMETRIC, FONTITALIC,
    OLE_YSIZE_CONTAINER, OLE_XPOS_PIXELS, OLE_OPTEXCLUSIVE,
    FONTSTRIKETHROUGH, OLE_YPOS_CONTAINER
)


class OLE_TRISTATE(IntFlag):
    Unchecked = 0
    Checked = 1
    Gray = 2


class LoadPictureConstants(IntFlag):
    Default = 0
    Monochrome = 1
    VgaColor = 2
    Color = 4


__all__ = [
    'IFont', 'StdPicture', 'Unchecked', 'OLE_XSIZE_HIMETRIC',
    'OLE_YSIZE_PIXELS', 'OLE_HANDLE', 'OLE_CANCELBOOL',
    'OLE_TRISTATE', 'IFontDisp', 'Checked', 'IPictureDisp',
    'OLE_COLOR', 'FontEvents', 'OLE_YPOS_HIMETRIC', 'Color',
    'typelib_path', 'Picture', 'Font', 'LoadPictureConstants',
    'FONTBOLD', 'FONTNAME', 'FONTUNDERSCORE', 'Default',
    'OLE_XSIZE_PIXELS', 'FONTSIZE', 'Monochrome', 'Library',
    'OLE_YPOS_PIXELS', 'OLE_YSIZE_HIMETRIC', 'Gray',
    'OLE_XPOS_CONTAINER', 'OLE_XPOS_HIMETRIC', 'FONTITALIC',
    'OLE_YSIZE_CONTAINER', 'FONTSTRIKETHROUGH', 'IFontEventsDisp',
    'OLE_XPOS_PIXELS', 'OLE_OPTEXCLUSIVE', 'OLE_ENABLEDEFAULTBOOL',
    'IPicture', 'VgaColor', 'StdFont', 'OLE_YPOS_CONTAINER',
    'OLE_XSIZE_CONTAINER'
]

