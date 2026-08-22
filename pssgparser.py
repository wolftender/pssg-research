import sys
import struct
import argparse
import pathlib
import logging
import json
import dataclasses
import ctypes
import math

from array import array
from enum import Enum, auto
from typing import Any, Optional, Union, Iterator, overload, NamedTuple
from dataclasses import dataclass, field

import wx
from wx import glcanvas

import OpenGL

OpenGL.ERROR_LOGGING = True
from OpenGL import GL

PSSG_MAGIC_NUMBER = 0x50535347  # "PSSG"


@dataclass
class Float2:
    x: float = 0.0
    y: float = 0.0


@dataclass
class Float3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Float4:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 0.0


class PssgElementType(Enum):
    UNKNOWN = 0
    NONE = 1
    FLOAT = 2
    INT = 3
    UINT = 4
    SHORT = 5
    USHORT = 6
    BYTE = 7
    HALF = 8


class PssgAttributeType(Enum):
    UNKNOWN = 0
    INT = 1
    STRING = 2
    FLOAT = 3
    FLOAT2 = 4
    FLOAT3 = 5
    FLOAT4 = 6


@dataclass
class PssgAttribute:
    id: int
    name: str
    type: PssgAttributeType
    value: Any


@dataclass
class PssgElement:
    id: int
    name: str
    type: PssgElementType
    value: Any
    attributes: list[PssgAttribute]
    children: list[PssgElement]

    def find_child(self, name: str) -> Optional[PssgElement]:
        for child in self.children:
            if child.name == name:
                return child

        for child in self.children:
            return child.find_child(name)

        return None

    def find_children(self, name: str) -> list[PssgElement]:
        found = []
        for child in self.children:
            if child.name == name:
                found.append(child)

        for child in self.children:
            found.extend(child.find_children(name))

        return found

    def find_attribute(self, name: str) -> Optional[PssgAttribute]:
        for attribute in self.attributes:
            if attribute.name == name:
                return attribute

        return None

    def get_attribute(self, name: str) -> PssgAttribute:
        attribute = self.find_attribute(name)
        if attribute is None:
            raise Exception(f"no attribute {name} found")

        return attribute


# this is for built-in types
@dataclass
class PssgBaseAttribute:
    element: str
    name: str
    type: PssgAttributeType


@dataclass
class PssgBaseElement:
    name: str
    type: PssgElementType


# this is for runtime types (custom per file)
@dataclass
class PssgSchemaAttribute:
    id: int = 0
    element_id: int = 0
    name: str = "NA"
    type: PssgAttributeType = PssgAttributeType.UNKNOWN


@dataclass
class PssgSchemaElement:
    id: int = 0
    name: str = "NA"
    type: PssgElementType = PssgElementType.UNKNOWN


# built-in data
BASE_ELEMENT_TYPES: list[PssgBaseElement] = [
    PssgBaseElement("BOUNDINGBOX", PssgElementType.FLOAT),
    PssgBaseElement("BUNDLENODE", PssgElementType.NONE),
    PssgBaseElement("CGSTREAM", PssgElementType.NONE),
    PssgBaseElement("CUBEMAPTEXTURE", PssgElementType.NONE),
    PssgBaseElement("DATA", PssgElementType.BYTE),
    PssgBaseElement("DATABLOCK", PssgElementType.NONE),
    PssgBaseElement("DATABLOCKDATA", PssgElementType.BYTE),
    PssgBaseElement("DATABLOCKSTREAM", PssgElementType.NONE),
    PssgBaseElement("PSSGDATABASE", PssgElementType.NONE),
    PssgBaseElement("FEATLASINFO", PssgElementType.NONE),
    PssgBaseElement("FEATLASINFODATA", PssgElementType.NONE),
    PssgBaseElement("INDEXSOURCEDATA", PssgElementType.BYTE),
    PssgBaseElement("INVERSEBINDMATRIX", PssgElementType.FLOAT),
    PssgBaseElement("JOINTNODE", PssgElementType.NONE),
    PssgBaseElement("LAYER", PssgElementType.NONE),
    PssgBaseElement("LIBRARY", PssgElementType.NONE),
    PssgBaseElement("LODNODE", PssgElementType.NONE),
    PssgBaseElement("LODRENDERINSTANCELIST", PssgElementType.NONE),
    PssgBaseElement("LODRENDERINSTANCES", PssgElementType.NONE),
    PssgBaseElement("LODRENDERNODE", PssgElementType.NONE),
    PssgBaseElement("LODSKINNODE", PssgElementType.NONE),
    PssgBaseElement("LODVISIBLERENDERNODE", PssgElementType.NONE),
    PssgBaseElement("MATRIXPALETTEBUNDLENODE", PssgElementType.NONE),
    PssgBaseElement("MATRIXPALETTEJOINTNODE", PssgElementType.NONE),
    PssgBaseElement("MATRIXPALETTEJOINTRENDERINSTANCE", PssgElementType.NONE),
    PssgBaseElement("MATRIXPALETTENODE", PssgElementType.NONE),
    PssgBaseElement("MATRIXPALETTERENDERINSTANCE", PssgElementType.NONE),
    PssgBaseElement("MATRIXPALETTESKINJOINT", PssgElementType.NONE),
    PssgBaseElement("MODIFIERNETWORKINSTANCE", PssgElementType.NONE),
    PssgBaseElement("MODIFIERNETWORKINSTANCECOMPILE", PssgElementType.NONE),
    PssgBaseElement("MODIFIERNETWORKINSTANCEMODIFIERINPUT", PssgElementType.NONE),
    PssgBaseElement("MODIFIERNETWORKINSTANCEUNIQUEMODIFIERINPUT", PssgElementType.UINT),
    PssgBaseElement("PNSTRING", PssgElementType.NONE),
    PssgBaseElement("NODE", PssgElementType.NONE),
    PssgBaseElement("XXX", PssgElementType.NONE),
    PssgBaseElement("RISTREAM", PssgElementType.NONE),
    PssgBaseElement("RENDERINSTANCESTREAM", PssgElementType.NONE),
    PssgBaseElement("RENDERDATASOURCE", PssgElementType.NONE),
    PssgBaseElement("RENDERINDEXSOURCE", PssgElementType.NONE),
    PssgBaseElement("RENDERINSTANCE", PssgElementType.NONE),
    PssgBaseElement("RENDERINSTANCESOURCE", PssgElementType.NONE),
    PssgBaseElement("RENDERINTERFACEBOUND", PssgElementType.NONE),
    PssgBaseElement("RENDERNODE", PssgElementType.NONE),
    PssgBaseElement("RENDERSTREAM", PssgElementType.NONE),
    PssgBaseElement("RENDERSTREAMINSTANCE", PssgElementType.NONE),
    PssgBaseElement("ROOTNODE", PssgElementType.NONE),
    PssgBaseElement("SEGMENTSET", PssgElementType.NONE),
    PssgBaseElement("SHADERGROUP", PssgElementType.NONE),
    PssgBaseElement("SHADERGROUPPASS", PssgElementType.BYTE),
    PssgBaseElement("SHADERINPUT", PssgElementType.FLOAT),
    PssgBaseElement("SHADERINPUTDEFINITION", PssgElementType.NONE),
    PssgBaseElement("SHADERINSTANCE", PssgElementType.NONE),
    PssgBaseElement("SHADERPROGRAM", PssgElementType.NONE),
    PssgBaseElement("SHADERPROGRAMCODE", PssgElementType.NONE),
    PssgBaseElement("SHADERPROGRAMCODEBLOCK", PssgElementType.BYTE),
    PssgBaseElement("SHADERSTREAMDEFINITION", PssgElementType.NONE),
    PssgBaseElement("SKELETON", PssgElementType.NONE),
    PssgBaseElement("SKINJOINT", PssgElementType.NONE),
    PssgBaseElement("SKINNODE", PssgElementType.NONE),
    PssgBaseElement("TEXTURE", PssgElementType.NONE),
    PssgBaseElement("TEXTUREIMAGE", PssgElementType.BYTE),
    PssgBaseElement("TEXTUREIMAGEBLOCK", PssgElementType.NONE),
    PssgBaseElement("TEXTUREIMAGEBLOCKDATA", PssgElementType.BYTE),
    PssgBaseElement("TEXTUREMIPMAP", PssgElementType.BYTE),
    PssgBaseElement("TRANSFORM", PssgElementType.FLOAT),
    PssgBaseElement("VISIBLERENDERNODE", PssgElementType.NONE),
]


BASE_ATTRIBUTE_TYPES: list[PssgBaseAttribute] = [
    PssgBaseAttribute("CGSTREAM", "cgStreamName", PssgAttributeType.STRING),
    PssgBaseAttribute("CGSTREAM", "cgStreamDataType", PssgAttributeType.STRING),
    PssgBaseAttribute("CGSTREAM", "cgStreamRenderType", PssgAttributeType.STRING),
    PssgBaseAttribute("DATABLOCK", "streamCount", PssgAttributeType.INT),
    PssgBaseAttribute("DATABLOCK", "size", PssgAttributeType.INT),
    PssgBaseAttribute("DATABLOCK", "elementCount", PssgAttributeType.INT),
    PssgBaseAttribute("DATABLOCKSTREAM", "renderType", PssgAttributeType.STRING),
    PssgBaseAttribute("DATABLOCKSTREAM", "dataType", PssgAttributeType.STRING),
    PssgBaseAttribute("DATABLOCKSTREAM", "offset", PssgAttributeType.INT),
    PssgBaseAttribute("DATABLOCKSTREAM", "stride", PssgAttributeType.INT),
    PssgBaseAttribute("PSSGDATABASE", "creator", PssgAttributeType.STRING),
    PssgBaseAttribute("PSSGDATABASE", "creationMachine", PssgAttributeType.STRING),
    PssgBaseAttribute("PSSGDATABASE", "creationDate", PssgAttributeType.STRING),
    PssgBaseAttribute("PSSGDATABASE", "scale", PssgAttributeType.FLOAT3),
    PssgBaseAttribute("PSSGDATABASE", "up", PssgAttributeType.FLOAT3),
    PssgBaseAttribute("FEATLASINFO", "atlasname", PssgAttributeType.STRING),
    PssgBaseAttribute("FEATLASINFO", "numberatlastextures", PssgAttributeType.INT),
    PssgBaseAttribute("FEATLASINFODATA", "texturename", PssgAttributeType.STRING),
    PssgBaseAttribute("FEATLASINFODATA", "u0", PssgAttributeType.FLOAT),
    PssgBaseAttribute("FEATLASINFODATA", "v0", PssgAttributeType.FLOAT),
    PssgBaseAttribute("FEATLASINFODATA", "u1", PssgAttributeType.FLOAT),
    PssgBaseAttribute("FEATLASINFODATA", "v1", PssgAttributeType.FLOAT),
    PssgBaseAttribute("LAYER", "name", PssgAttributeType.STRING),
    PssgBaseAttribute("LIBRARY", "type", PssgAttributeType.STRING),
    PssgBaseAttribute("LODRENDERINSTANCELIST", "lod", PssgAttributeType.FLOAT),
    PssgBaseAttribute("LODRENDERINSTANCES", "lodCount", PssgAttributeType.INT),
    PssgBaseAttribute(
        "MATRIXPALETTEJOINTNODE", "matrixPalette", PssgAttributeType.STRING
    ),
    PssgBaseAttribute("MATRIXPALETTEJOINTNODE", "jointID", PssgAttributeType.INT),
    PssgBaseAttribute(
        "MATRIXPALETTEJOINTRENDERINSTANCE", "streamOffset", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MATRIXPALETTEJOINTRENDERINSTANCE",
        "elementCountFromOffset",
        PssgAttributeType.INT,
    ),
    PssgBaseAttribute(
        "MATRIXPALETTEJOINTRENDERINSTANCE", "indexOffset", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MATRIXPALETTEJOINTRENDERINSTANCE",
        "indicesCountFromOffset",
        PssgAttributeType.INT,
    ),
    PssgBaseAttribute(
        "MATRIXPALETTEJOINTRENDERINSTANCE", "jointID", PssgAttributeType.INT
    ),
    PssgBaseAttribute("MATRIXPALETTENODE", "jointCount", PssgAttributeType.INT),
    PssgBaseAttribute(
        "MATRIXPALETTERENDERINSTANCE", "streamOffset", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MATRIXPALETTERENDERINSTANCE", "elementCountFromOffset", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MATRIXPALETTERENDERINSTANCE", "indexOffset", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MATRIXPALETTERENDERINSTANCE", "indicesCountFromOffset", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MATRIXPALETTERENDERINSTANCE", "jointCount", PssgAttributeType.INT
    ),
    PssgBaseAttribute("MATRIXPALETTESKINJOINT", "joint", PssgAttributeType.STRING),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCE", "dynamicStreamCount", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCE", "modifierInputCount", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCE", "parameterCount", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCE", "modifierCount", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCE", "packetModifierCount", PssgAttributeType.INT
    ),
    PssgBaseAttribute("MODIFIERNETWORKINSTANCE", "network", PssgAttributeType.STRING),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCECOMPILE", "uniqueInputCount", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCECOMPILE", "packetCount", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCECOMPILE", "maxElementCount", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCECOMPILE", "memorySizeForProcess", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCECOMPILE", "maxPacketOutputSize", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCECOMPILE",
        "maxTemporaryBufferSize",
        PssgAttributeType.INT,
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCECOMPILE", "stateBlockBufferSize", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCECOMPILE", "totalInputPacketSize", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCECOMPILE", "packetSizeCount", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCECOMPILE",
        "packetModifierInputCount",
        PssgAttributeType.INT,
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCECOMPILE", "infoPacketSize", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCEMODIFIERINPUT", "source", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "MODIFIERNETWORKINSTANCEMODIFIERINPUT", "stream", PssgAttributeType.INT
    ),
    PssgBaseAttribute("PNSTRING", "data", PssgAttributeType.STRING),
    PssgBaseAttribute("PNSTRING", "size", PssgAttributeType.INT),
    PssgBaseAttribute("NODE", "stopTraversal", PssgAttributeType.INT),
    PssgBaseAttribute("NODE", "nickname", PssgAttributeType.STRING),
    PssgBaseAttribute("XXX", "id", PssgAttributeType.STRING),
    PssgBaseAttribute("RISTREAM", "id", PssgAttributeType.INT),
    PssgBaseAttribute("RISTREAM", "stream", PssgAttributeType.STRING),
    PssgBaseAttribute("RENDERINSTANCESTREAM", "sourceID", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERINSTANCESTREAM", "streamID", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERDATASOURCE", "streamCount", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERDATASOURCE", "packetCount", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERDATASOURCE", "packetListCount", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERDATASOURCE", "primitive", PssgAttributeType.STRING),
    PssgBaseAttribute("RENDERINDEXSOURCE", "primitive", PssgAttributeType.STRING),
    PssgBaseAttribute("RENDERINDEXSOURCE", "minimumIndex", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERINDEXSOURCE", "maximumIndex", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERINDEXSOURCE", "format", PssgAttributeType.STRING),
    PssgBaseAttribute("RENDERINDEXSOURCE", "count", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERINSTANCE", "streamCount", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERINSTANCE", "shader", PssgAttributeType.STRING),
    PssgBaseAttribute("RENDERINSTANCESOURCE", "source", PssgAttributeType.STRING),
    PssgBaseAttribute("RENDERINTERFACEBOUND", "localData", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERINTERFACEBOUND", "isRenderTarget", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERINTERFACEBOUND", "allocateSystem", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERINTERFACEBOUND", "prioritizeRead", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERINTERFACEBOUND", "automaticBind", PssgAttributeType.INT),
    PssgBaseAttribute(
        "RENDERINTERFACEBOUND", "discardLocalAfterBind", PssgAttributeType.INT
    ),
    PssgBaseAttribute("RENDERSTREAM", "dataBlock", PssgAttributeType.STRING),
    PssgBaseAttribute("RENDERSTREAM", "subStream", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERSTREAMINSTANCE", "sourceCount", PssgAttributeType.INT),
    PssgBaseAttribute("RENDERSTREAMINSTANCE", "indices", PssgAttributeType.STRING),
    PssgBaseAttribute("SEGMENTSET", "segmentCount", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUP", "parameterCount", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUP", "parameterSavedCount", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUP", "parameterStreamCount", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUP", "instancesRequireSorting", PssgAttributeType.INT),
    PssgBaseAttribute(
        "SHADERGROUP", "defaultRenderSortPriority", PssgAttributeType.INT
    ),
    PssgBaseAttribute("SHADERGROUP", "passCount", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "vertexProgram", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "fragmentProgram", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "hullProgram", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "domainProgram", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "blendEnable", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "blendSource", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "blendDest", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "blendOp", PssgAttributeType.STRING),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "separateAlphaBlendEnable", PssgAttributeType.INT
    ),
    PssgBaseAttribute("SHADERGROUPPASS", "blendSourceAlpha", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "blendDestAlpha", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "blendOpAlpha", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "alphaTestEnable", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "alphaTestFunc", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "alphaTestRef", PssgAttributeType.FLOAT),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "alphaToCoverageEnable", PssgAttributeType.INT
    ),
    PssgBaseAttribute("SHADERGROUPPASS", "alphaToCoverageLevel", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "depthTestEnable", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "depthTestFunc", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "depthMaskEnable", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "cullFaceType", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "polyFillType", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERGROUPPASS", "polyOffsetEnable", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "polyOffsetFactor", PssgAttributeType.FLOAT),
    PssgBaseAttribute("SHADERGROUPPASS", "polyOffsetUnits", PssgAttributeType.FLOAT),
    PssgBaseAttribute("SHADERGROUPPASS", "colorMaskRed", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "colorMaskGreen", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "colorMaskBlue", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "colorMaskAlpha", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "stencilMode", PssgAttributeType.STRING),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilFrontFunc", PssgAttributeType.STRING
    ),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilFrontRef", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilFrontMask", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilFrontFailOp", PssgAttributeType.STRING
    ),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilFrontZFailOp", PssgAttributeType.STRING
    ),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilFrontZPassOp", PssgAttributeType.STRING
    ),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilFrontStencilMask", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilBackFunc", PssgAttributeType.STRING
    ),
    PssgBaseAttribute("SHADERGROUPPASS", "2SidedStencilBackRef", PssgAttributeType.INT),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilBackMask", PssgAttributeType.INT
    ),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilBackFailOp", PssgAttributeType.STRING
    ),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilBackZFailOp", PssgAttributeType.STRING
    ),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilBackZPassOp", PssgAttributeType.STRING
    ),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "2SidedStencilBackStencilMask", PssgAttributeType.INT
    ),
    PssgBaseAttribute("SHADERGROUPPASS", "normalizeEnable", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "passConfigMaskLow", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "passConfigMaskHigh", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERGROUPPASS", "polySmoothEnable", PssgAttributeType.INT),
    PssgBaseAttribute(
        "SHADERGROUPPASS", "coupleVertexAndPixelProgram", PssgAttributeType.INT
    ),
    PssgBaseAttribute("SHADERINPUT", "parameterID", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERINPUT", "type", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERINPUT", "format", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERINPUT", "custom", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERINPUT", "texture", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERINPUT", "light", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERINPUT", "object", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERINPUTDEFINITION", "name", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERINPUTDEFINITION", "type", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERINPUTDEFINITION", "format", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERINSTANCE", "shaderGroup", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERINSTANCE", "parameterCount", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERINSTANCE", "parameterSavedCount", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERINSTANCE", "renderSortPriority", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERPROGRAM", "codeCount", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERPROGRAMCODE", "codeSize", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERPROGRAMCODE", "codeType", PssgAttributeType.STRING),
    PssgBaseAttribute("SHADERPROGRAMCODE", "profileType", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERPROGRAMCODE", "profile", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERPROGRAMCODE", "codeEntry", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERPROGRAMCODE", "parameterCount", PssgAttributeType.INT),
    PssgBaseAttribute("SHADERPROGRAMCODE", "streamCount", PssgAttributeType.INT),
    PssgBaseAttribute(
        "SHADERSTREAMDEFINITION", "renderTypeName", PssgAttributeType.STRING
    ),
    PssgBaseAttribute("SHADERSTREAMDEFINITION", "name", PssgAttributeType.STRING),
    PssgBaseAttribute("SKELETON", "matrixCount", PssgAttributeType.INT),
    PssgBaseAttribute("SKINJOINT", "joint", PssgAttributeType.STRING),
    PssgBaseAttribute("SKINNODE", "jointCount", PssgAttributeType.INT),
    PssgBaseAttribute("SKINNODE", "skeleton", PssgAttributeType.STRING),
    PssgBaseAttribute("SKINNODE", "updateBounds", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "width", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "height", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "depth", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "texelFormat", PssgAttributeType.STRING),
    PssgBaseAttribute("TEXTURE", "transient", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "wrapS", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "wrapT", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "wrapR", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "minFilter", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "magFilter", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "automipmap", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "numberMipMapLevels", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "msaaType", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "gammaRemapR", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "gammaRemapG", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "gammaRemapB", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "gammaRemapA", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "enableCompare", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "maxAnisotropy", PssgAttributeType.FLOAT),
    PssgBaseAttribute("TEXTURE", "lodBias", PssgAttributeType.FLOAT),
    PssgBaseAttribute("TEXTURE", "enableVertexTexture", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "borderColor", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "imageBlockCount", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTURE", "mipZeroAbsent", PssgAttributeType.INT),
    PssgBaseAttribute("TEXTUREIMAGEBLOCK", "typename", PssgAttributeType.STRING),
    PssgBaseAttribute("TEXTUREIMAGEBLOCK", "size", PssgAttributeType.INT),
]


def pssg_find_element_type(element_name: str) -> PssgElementType:
    for base_element in BASE_ELEMENT_TYPES:
        if base_element.name == element_name:
            return base_element.type

    return PssgElementType.UNKNOWN


def pssg_find_attribute_type(
    element_name: str, attribute_name: str
) -> PssgAttributeType:
    for base_attribute in BASE_ATTRIBUTE_TYPES:
        if (
            base_attribute.element == element_name
            and base_attribute.name == attribute_name
        ):
            return base_attribute.type

    return PssgAttributeType.UNKNOWN


class PssgReader:
    def __init__(self, filename: str):
        self.file_name = filename
        self._read_whole_file()

    def _pssg_read_u8(self) -> int:
        value = struct.unpack_from(">B", self.pssg_buffer, self.buffer_offset)[0]
        self.buffer_offset += 1
        return value

    def _pssg_read_s8(self) -> int:
        value = struct.unpack_from(">b", self.pssg_buffer, self.buffer_offset)[0]
        self.buffer_offset += 1
        return value

    def _pssg_read_u16(self) -> int:
        value = struct.unpack_from(">H", self.pssg_buffer, self.buffer_offset)[0]
        self.buffer_offset += 2
        return value

    def _pssg_read_s16(self) -> int:
        value = struct.unpack_from(">h", self.pssg_buffer, self.buffer_offset)[0]
        self.buffer_offset += 2
        return value

    def _pssg_read_u32(self) -> int:
        value = struct.unpack_from(">I", self.pssg_buffer, self.buffer_offset)[0]
        self.buffer_offset += 4
        return value

    def _pssg_read_s32(self) -> int:
        value = struct.unpack_from(">i", self.pssg_buffer, self.buffer_offset)[0]
        self.buffer_offset += 4
        return value

    def _pssg_read_float(self) -> float:
        value = struct.unpack_from(">f", self.pssg_buffer, self.buffer_offset)[0]
        self.buffer_offset += 4
        return value

    def _pssg_read_half(self) -> float:
        value = struct.unpack_from(">e", self.pssg_buffer, self.buffer_offset)[0]
        self.buffer_offset += 2
        return value

    def _pssg_read_double(self) -> float:
        value = struct.unpack_from(">d", self.pssg_buffer, self.buffer_offset)[0]
        self.buffer_offset += 8
        return value

    def _pssg_read_fixed_string(self, length: int) -> str:
        value = struct.unpack_from(f">{length}s", self.pssg_buffer, self.buffer_offset)[
            0
        ]
        self.buffer_offset += length
        return value.rstrip(b"\x00").decode("utf-8")

    def _pssg_read_string(self) -> str:
        len = self._pssg_read_u32()
        return self._pssg_read_fixed_string(len)

    def _pssg_read_n_bytes(self, n: int) -> bytes:
        value = struct.unpack_from(f">{n}s", self.pssg_buffer, self.buffer_offset)[0]
        self.buffer_offset += n
        return value

    def _pssg_read_n_u8(self, n: int) -> bytes:
        values = struct.unpack_from(f">{n}s", self.pssg_buffer, self.buffer_offset)[0]
        self.buffer_offset += n
        return values

    def _pssg_read_n_s8(self, n: int) -> tuple[int, ...]:
        values = struct.unpack_from(f">{n}b", self.pssg_buffer, self.buffer_offset)
        self.buffer_offset += n
        return values

    def _pssg_read_n_u16(self, n: int) -> tuple[int, ...]:
        values = struct.unpack_from(f">{n}H", self.pssg_buffer, self.buffer_offset)
        self.buffer_offset += n * 2
        return values

    def _pssg_read_n_s16(self, n: int) -> tuple[int, ...]:
        values = struct.unpack_from(f">{n}h", self.pssg_buffer, self.buffer_offset)
        self.buffer_offset += n * 2
        return values

    def _pssg_read_n_u32(self, n: int) -> tuple[int, ...]:
        values = struct.unpack_from(f">{n}I", self.pssg_buffer, self.buffer_offset)
        self.buffer_offset += n * 4
        return values

    def _pssg_read_n_s32(self, n: int) -> tuple[int, ...]:
        values = struct.unpack_from(f">{n}i", self.pssg_buffer, self.buffer_offset)
        self.buffer_offset += n * 4
        return values

    def _pssg_read_n_float(self, n: int) -> tuple[float, ...]:
        values = struct.unpack_from(f">{n}f", self.pssg_buffer, self.buffer_offset)
        self.buffer_offset += n * 4
        return values

    def _pssg_read_n_double(self, n: int) -> tuple[float, ...]:
        values = struct.unpack_from(f">{n}d", self.pssg_buffer, self.buffer_offset)
        self.buffer_offset += n * 8
        return values

    def _pssg_read_n_half(self, n: int) -> tuple[float, ...]:
        values = struct.unpack_from(f">{n}e", self.pssg_buffer, self.buffer_offset)
        self.buffer_offset += n * 2
        return values

    def _read_whole_file(self):
        self.file_path = pathlib.Path(self.file_name)

        if not self.file_path.is_file():
            raise Exception(f"{self.file_name} is not a valid path")

        with open(self.file_path, "rb") as stream:
            self.pssg_buffer = stream.read()

        self._pssg_parse_buffer()

    def _pssg_parse_buffer(self):
        self.buffer_offset = 0

        magic = self._pssg_read_u32()
        if magic != PSSG_MAGIC_NUMBER:
            raise Exception("invalid pssg file: magic number mismatch")

        pssg_size = self._pssg_read_u32()
        pssg_buffer_size = len(self.pssg_buffer)
        if pssg_buffer_size < pssg_size:
            raise Exception(
                f"invalid pssg file: filesize mismatch, reported {pssg_size}, have {pssg_buffer_size}"
            )

        self._pssg_parse_schema()
        self.pssg_tree = self._pssg_parse_element()

    def _pssg_parse_schema(self):
        pssg_num_attribs = self._pssg_read_u32()
        pssg_num_elements = self._pssg_read_u32()

        self.pssg_schema_attribs = [
            PssgSchemaAttribute() for _ in range(pssg_num_attribs)
        ]
        self.pssg_schema_elements = [
            PssgSchemaElement() for _ in range(pssg_num_elements)
        ]

        for _ in range(pssg_num_elements):
            pssg_element_id = self._pssg_read_u32()
            pssg_element_name = self._pssg_read_string()

            if pssg_element_id > pssg_num_elements:
                raise Exception(f"invalid pssg element id {pssg_element_id}")

            pssg_schema_element = self.pssg_schema_elements[pssg_element_id - 1]
            pssg_schema_element.id = pssg_element_id
            pssg_schema_element.name = pssg_element_name
            pssg_schema_element.type = pssg_find_element_type(pssg_element_name)

            pssg_num_sub_attributes = self._pssg_read_u32()
            for _ in range(pssg_num_sub_attributes):
                pssg_attrib_id = self._pssg_read_u32()
                pssg_attrib_name = self._pssg_read_string()

                if pssg_attrib_id > pssg_num_attribs:
                    raise Exception(f"invalid pssg attribute id {pssg_attrib_id}")

                pssg_schema_attrib = self.pssg_schema_attribs[pssg_attrib_id - 1]
                pssg_schema_attrib.id = pssg_attrib_id
                pssg_schema_attrib.name = pssg_attrib_name
                pssg_schema_attrib.element_id = pssg_element_id
                pssg_schema_attrib.type = pssg_find_attribute_type(
                    pssg_element_name, pssg_attrib_name
                )

    def _pssg_parse_element_value(self, type: PssgElementType, size: int) -> Any:
        match type:
            case PssgElementType.UNKNOWN:
                return self._pssg_read_n_bytes(size)

            case PssgElementType.NONE:
                return self._pssg_read_n_bytes(size)

            case PssgElementType.FLOAT:
                num_elements = size // 4
                return self._pssg_read_n_float(num_elements)

            case PssgElementType.INT:
                num_elements = size // 4
                return self._pssg_read_n_s32(num_elements)

            case PssgElementType.UINT:
                num_elements = size // 4
                return self._pssg_read_n_u32(num_elements)

            case PssgElementType.SHORT:
                num_elements = size // 2
                return self._pssg_read_n_s16(num_elements)

            case PssgElementType.USHORT:
                num_elements = size // 2
                return self._pssg_read_n_u16(num_elements)

            case PssgElementType.BYTE:
                num_elements = size
                return self._pssg_read_n_u8(num_elements)

            case PssgElementType.HALF:
                num_elements = size // 2
                return self._pssg_read_n_half(num_elements)

            case _:
                self.buffer_offset += size
                return None

    def _pssg_parse_attrib_value(self, type: PssgAttributeType, size: int) -> Any:
        match type:
            case PssgAttributeType.UNKNOWN:
                return self._pssg_read_n_bytes(size)

            case PssgAttributeType.INT:
                return self._pssg_read_s32()

            case PssgAttributeType.STRING:
                return self._pssg_read_string()

            case PssgAttributeType.FLOAT:
                return self._pssg_read_float()

            case PssgAttributeType.FLOAT2:
                value = Float2()
                value.x = self._pssg_read_float()
                value.y = self._pssg_read_float()

                return value

            case PssgAttributeType.FLOAT3:
                value = Float3()
                value.x = self._pssg_read_float()
                value.y = self._pssg_read_float()
                value.z = self._pssg_read_float()

                return value

            case PssgAttributeType.FLOAT4:
                value = Float4()
                value.x = self._pssg_read_float()
                value.y = self._pssg_read_float()
                value.z = self._pssg_read_float()
                value.w = self._pssg_read_float()

                return value

            case _:
                self.buffer_offset += size
                return None

    def _pssg_check_children(self, element_end_offset: int) -> bool:
        data_end_offset = element_end_offset
        while self.buffer_offset < data_end_offset:
            pssg_element_id = self._pssg_read_u32()

            if pssg_element_id > len(self.pssg_schema_elements):
                return False

            pssg_element_size = self._pssg_read_u32()
            remaining_bytes = data_end_offset - self.buffer_offset
            if remaining_bytes < pssg_element_size:
                return False

            self.buffer_offset += pssg_element_size

        return True

    def _pssg_parse_element(self) -> PssgElement:
        pssg_element_id = self._pssg_read_u32()
        pssg_element_size = self._pssg_read_u32()
        pssg_element_end_offs = self.buffer_offset + pssg_element_size
        pssg_element_attr_size = self._pssg_read_u32()

        if pssg_element_id > len(self.pssg_schema_elements):
            raise Exception(
                f"pssg element id at {self.buffer_offset} is invalid ({pssg_element_id})"
            )

        pssg_schema_element = self.pssg_schema_elements[pssg_element_id - 1]

        pssg_element = PssgElement(
            id=pssg_element_id,
            name=pssg_schema_element.name,
            type=pssg_schema_element.type,
            value=None,
            attributes=[],
            children=[],
        )

        attrib_end_offs = self.buffer_offset + pssg_element_attr_size
        while self.buffer_offset < attrib_end_offs:
            pssg_attrib_id = self._pssg_read_u32()
            pssg_attrib_size = self._pssg_read_u32()
            pssg_attrib_end_offs = self.buffer_offset + pssg_attrib_size

            if pssg_attrib_id > len(self.pssg_schema_attribs):
                raise Exception(
                    f"pssg attrib id at {self.buffer_offset} is invalid ({pssg_attrib_id})"
                )

            pssg_schema_attrib = self.pssg_schema_attribs[pssg_attrib_id - 1]
            pssg_attrib_value = self._pssg_parse_attrib_value(
                pssg_schema_attrib.type, pssg_attrib_size
            )

            pssg_attrib = PssgAttribute(
                id=pssg_attrib_id,
                name=pssg_schema_attrib.name,
                type=pssg_schema_attrib.type,
                value=pssg_attrib_value,
            )

            pssg_element.attributes.append(pssg_attrib)
            self.buffer_offset = pssg_attrib_end_offs

        pssg_element_data_start_offset = self.buffer_offset

        # this is fallback logic from ego engine modding tools
        has_valid_subtree = True

        # same as xml, if it has primitive value type like str or int
        # then it will not have a subtree
        if (
            pssg_schema_element.type != PssgElementType.NONE
            and pssg_schema_element.type != PssgElementType.UNKNOWN
        ):
            has_valid_subtree = False

        if has_valid_subtree:
            has_valid_subtree = self._pssg_check_children(pssg_element_end_offs)

        if has_valid_subtree:
            self.buffer_offset = pssg_element_data_start_offset
            try:
                while self.buffer_offset < pssg_element_end_offs:
                    pssg_child_element = self._pssg_parse_element()
                    pssg_element.children.append(pssg_child_element)
            except:
                logging.warning(
                    f"failed to parse element {pssg_schema_element.name}, save as raw buffer"
                )
                has_valid_subtree = False

        if not has_valid_subtree:
            self.buffer_offset = pssg_element_data_start_offset
            element_data_size = pssg_element_end_offs - self.buffer_offset
            pssg_element.value = self._pssg_parse_element_value(
                pssg_schema_element.type, element_data_size
            )

        self.buffer_offset = pssg_element_end_offs
        return pssg_element


def pssg_find_texture_block(root: PssgElement, id: str) -> Optional[PssgElement]:
    libraries = root.find_children("LIBRARY")
    for library in libraries:
        library_type = library.find_attribute("type")
        if library_type is None:
            continue

        if library_type.value == "RENDERINTERFACEBOUND":
            textures = library.find_children("TEXTURE")
            for texture in textures:
                texture_id = texture.find_attribute("id")
                if texture_id is None:
                    continue

                if texture_id.value == id:
                    return texture

    return None


class PssgDecodedTexture:
    def __init__(self, element: PssgElement):
        if element.name != "TEXTURE":
            raise Exception(
                f"cannot decode a texture from an element of type {element.name}"
            )

        self.id = str(element.get_attribute("id").value)
        self.width = int(element.get_attribute("width").value)
        self.height = int(element.get_attribute("height").value)
        self.texel_format = str(element.get_attribute("texelFormat").value)

        image_block = element.find_child("TEXTUREIMAGEBLOCK")
        if image_block is None:
            raise Exception("texture has no image block")

        image_block_data = image_block.find_child("TEXTUREIMAGEBLOCKDATA")
        if image_block_data is None:
            raise Exception("texture image block has no data")

        if self.texel_format == "dxt1":
            self._decode_texels_dxt1(image_block_data.value)
        else:
            raise Exception(f"unknown texel format {self.texel_format}")

    @classmethod
    def _unpack_rgb565(cls, packed: int) -> tuple[int, int, int, int]:
        r = (packed >> 11) & 0x1F
        g = (packed >> 5) & 0x3F
        b = (packed) & 0x1F

        r = (r << 3) | (r >> 2)
        g = (g << 2) | (g >> 4)
        b = (b << 3) | (b >> 2)

        return (r, g, b, 255)

    def _decode_texels_dxt1(self, value: bytes):
        block_count_x = self.width // 4
        block_count_y = self.height // 4

        self.texels = bytearray(self.width * self.height * 4)  # rgba
        buffer_offset = 0

        for row in range(block_count_y):
            for col in range(block_count_x):
                c0_packed = struct.unpack_from("<H", value, buffer_offset)[0]
                buffer_offset += 2

                c1_packed = struct.unpack_from("<H", value, buffer_offset)[0]
                buffer_offset += 2

                ctable = struct.unpack_from("<I", value, buffer_offset)[0]
                buffer_offset += 4

                c0 = self._unpack_rgb565(c0_packed)
                c1 = self._unpack_rgb565(c1_packed)

                r0 = c0[0]
                g0 = c0[1]
                b0 = c0[2]
                r1 = c1[0]
                g1 = c1[1]
                b1 = c1[2]

                if c0_packed > c1_packed:
                    c2 = (
                        (2 * r0 + r1) // 3,
                        (2 * g0 + g1) // 3,
                        (2 * b0 + b1) // 3,
                        255,
                    )
                    c3 = (
                        (r0 + 2 * r1) // 3,
                        (g0 + 2 * g1) // 3,
                        (b0 + 2 * b1) // 3,
                        255,
                    )
                else:
                    c2 = ((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, 255)
                    c3 = (0, 0, 0, 255)

                for j in range(4):
                    for i in range(4):
                        code = (ctable >> (2 * (4 * i + j))) & 0x03
                        x = (col * 4) + j
                        y = (row * 4) + i
                        idx = (y * self.width + x) * 4
                        color = [c0, c1, c2, c3][code]
                        self.texels[idx + 0] = color[0]
                        self.texels[idx + 1] = color[1]
                        self.texels[idx + 2] = color[2]
                        self.texels[idx + 3] = color[3]


class Vector3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float)]

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        super().__init__(x, y, z)

    @classmethod
    def zero(cls) -> Vector3:
        return cls(0.0, 0.0, 0.0)

    @classmethod
    def from_seq(cls, values: tuple[float, float, float]) -> Vector3:
        return cls(values[0], values[1], values[2])

    def __add__(self, other: Vector3) -> Vector3:
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vector3) -> Vector3:
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, s: float) -> Vector3:
        return Vector3(self.x * s, self.y * s, self.z * s)

    def __rmul__(self, s: float) -> Vector3:
        return self.__mul__(s)

    def __neg__(self) -> Vector3:
        return Vector3(-self.x, -self.y, -self.z)

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y
        yield self.z

    def __repr__(self) -> str:
        return f"Vector3({self.x:.3f}, {self.y:.3f}, {self.z:.3f})"

    def dot(self, other: Vector3) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vector3) -> Vector3:
        return Vector3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length(self) -> float:
        return math.sqrt(self.dot(self))

    def normalize(self) -> Vector3:
        l = self.length()
        return Vector3(self.x / l, self.y / l, self.z / l)

    def lerp(self, other: Vector3, t: float) -> Vector3:
        return Vector3(
            self.x + (other.x - self.x) * t,
            self.y + (other.y - self.y) * t,
            self.z + (other.z - self.z) * t,
        )


class Matrix4x4(ctypes.Structure):
    _fields_ = [("values", ctypes.c_float * 16)]

    def __init__(self, values: tuple[float, ...] | None = None) -> None:
        if values is None:
            values = (0.0,) * 16
        super().__init__(values)

    @classmethod
    def identity(cls) -> Matrix4x4:
        # fmt: off
        return cls((
            1, 0, 0, 0,
            0, 1, 0, 0,
            0, 0, 1, 0,
            0, 0, 0, 1,
        ))
        # fmt: on

    @classmethod
    def translation(cls, v: Vector3) -> Matrix4x4:
        # fmt: off
        return cls((
            1, 0, 0, v.x,
            0, 1, 0, v.y,
            0, 0, 1, v.z,
            0, 0, 0, 1,
        ))
        # fmt: on

    @classmethod
    def scale(cls, v: Vector3) -> Matrix4x4:
        # fmt: off
        return cls((
            v.x, 0, 0, 0,
            0, v.y, 0, 0,
            0, 0, v.z, 0,
            0, 0, 0, 1,
        ))
        #fmt: on

    @classmethod
    def rotation_x(cls, angle: float) -> Matrix4x4:
        c, s = math.cos(angle), math.sin(angle)

        # fmt: off
        return cls((
            1, 0, 0, 0,
            0, c, -s, 0,
            0, s, c, 0,
            0, 0, 0, 1,
        ))
        # fmt: on

    @classmethod
    def rotation_y(cls, angle: float) -> Matrix4x4:
        c, s = math.cos(angle), math.sin(angle)

        # fmt: off
        return cls((
            c, 0, s, 0,
            0, 1, 0, 0,
            -s, 0, c, 0,
            0, 0, 0, 1,
        ))
        # fmt: on

    @classmethod
    def rotation_z(cls, angle: float) -> Matrix4x4:
        c, s = math.cos(angle), math.sin(angle)

        # fmt: off
        return cls((
            c, -s, 0, 0,
            s, c, 0, 0,
            0, 0, 1, 0,
            0, 0, 0, 1,
        ))
        # fmt: on

    @classmethod
    def perspective(
        cls, aspect: float, fov: float, near: float, far: float
    ) -> Matrix4x4:
        t = math.tan(fov / 2.0)
        zm = far - near
        zp = far + near

        # fmt: off
        return cls((
            1 / (t * aspect), 0, 0, 0,
            0, 1 / t, 0, 0,
            0, 0, -zp / zm, -(2 * far * near) / zm,
            0, 0, -1, 0,
        ))
        # fmt: on

    def __getitem__(self, i: int) -> float:
        return self.values[i]

    def __setitem__(self, i: int, v: float) -> None:
        self.values[i] = v

    def __iter__(self) -> Iterator[float]:
        return iter(self.values)

    def __repr__(self) -> str:
        rows = [self.values[i : i + 4] for i in range(0, 16, 4)]
        return "\n".join(" ".join(f"{v: .3f}" for v in row) for row in rows)

    def __add__(self, other: Matrix4x4) -> Matrix4x4:
        return Matrix4x4(tuple(a + b for a, b in zip(self.values, other.values)))

    def __sub__(self, other: Matrix4x4) -> Matrix4x4:
        return Matrix4x4(tuple(a - b for a, b in zip(self.values, other.values)))

    @overload
    def __mul__(self, other: Matrix4x4) -> Matrix4x4: ...
    @overload
    def __mul__(self, other: Vector3) -> Vector3: ...
    @overload
    def __mul__(self, other: float) -> Matrix4x4: ...

    def __mul__(
        self, other: Union[Matrix4x4, Vector3, float]
    ) -> Union[Matrix4x4, Vector3]:
        if isinstance(other, Matrix4x4):
            return self._mul_matrix(other)

        if isinstance(other, Vector3):
            return self._mul_vector(other)

        if isinstance(other, (int, float)):
            return Matrix4x4(tuple(v * other for v in self.values))

        raise NotImplementedError()

    def __rmul__(self, s: float) -> Matrix4x4:
        return Matrix4x4(tuple(v * s for v in self.values))

    def _mul_matrix(self, b: Matrix4x4) -> Matrix4x4:
        a = self.values
        bv = b.values

        # fmt: off
        return Matrix4x4((
            a[0]*bv[0]+a[1]*bv[4]+a[2]*bv[8]+a[3]*bv[12],
            a[0]*bv[1]+a[1]*bv[5]+a[2]*bv[9]+a[3]*bv[13],
            a[0]*bv[2]+a[1]*bv[6]+a[2]*bv[10]+a[3]*bv[14],
            a[0]*bv[3]+a[1]*bv[7]+a[2]*bv[11]+a[3]*bv[15],

            a[4]*bv[0]+a[5]*bv[4]+a[6]*bv[8]+a[7]*bv[12],
            a[4]*bv[1]+a[5]*bv[5]+a[6]*bv[9]+a[7]*bv[13],
            a[4]*bv[2]+a[5]*bv[6]+a[6]*bv[10]+a[7]*bv[14],
            a[4]*bv[3]+a[5]*bv[7]+a[6]*bv[11]+a[7]*bv[15],

            a[8]*bv[0]+a[9]*bv[4]+a[10]*bv[8]+a[11]*bv[12],
            a[8]*bv[1]+a[9]*bv[5]+a[10]*bv[9]+a[11]*bv[13],
            a[8]*bv[2]+a[9]*bv[6]+a[10]*bv[10]+a[11]*bv[14],
            a[8]*bv[3]+a[9]*bv[7]+a[10]*bv[11]+a[11]*bv[15],

            a[12]*bv[0]+a[13]*bv[4]+a[14]*bv[8]+a[15]*bv[12],
            a[12]*bv[1]+a[13]*bv[5]+a[14]*bv[9]+a[15]*bv[13],
            a[12]*bv[2]+a[13]*bv[6]+a[14]*bv[10]+a[15]*bv[14],
            a[12]*bv[3]+a[13]*bv[7]+a[14]*bv[11]+a[15]*bv[15],
        ))
        # fmt: on

    def _mul_vector(self, v: Vector3, w: float = 1.0) -> Vector3:
        t = self.values
        return Vector3(
            t[0] * v.x + t[1] * v.y + t[2] * v.z + t[3] * w,
            t[4] * v.x + t[5] * v.y + t[6] * v.z + t[7] * w,
            t[8] * v.x + t[9] * v.y + t[10] * v.z + t[11] * w,
        )

    def transpose(self) -> Matrix4x4:
        a = self.values

        # fmt: off
        return Matrix4x4((
            a[0], a[4], a[8], a[12],
            a[1], a[5], a[9], a[13],
            a[2], a[6], a[10], a[14],
            a[3], a[7], a[11], a[15],
        ))
        # fmt: on

    def decompose(self) -> tuple[Vector3, Quaternion, Vector3]:
        m = self.values

        translation = Vector3(m[3], m[7], m[11])

        # basis vectors
        col0 = Vector3(m[0], m[4], m[8])
        col1 = Vector3(m[1], m[5], m[9])
        col2 = Vector3(m[2], m[6], m[10])

        sx = col0.length()
        sy = col1.length()
        sz = col2.length()

        # don't handle degenerated cases
        if sx == 0 or sy == 0 or sz == 0:
            return (Vector3.zero(), Quaternion.identity(), Vector3.zero())

        det3x3 = (
            m[0] * (m[5] * m[10] - m[6] * m[9])
            - m[1] * (m[4] * m[10] - m[6] * m[8])
            + m[2] * (m[4] * m[9] - m[5] * m[8])
        )
        if det3x3 < 0:
            sx = -sx

        col0 = col0 * (1 / sx)
        col1 = col1 * (1 / sy)
        col2 = col2 * (1 / sz)

        # SO(3) group matrix - det == 1
        # fmt: off
        rot_matrix = Matrix4x4((
            col0.x, col1.x, col2.x, 0,
            col0.y, col1.y, col2.y, 0,
            col0.z, col1.z, col2.z, 0,
            0, 0, 0, 1,
        ))
        # fmt: on

        rotation = Quaternion.from_matrix(rot_matrix)
        return (translation, rotation, Vector3(sx, sy, sz))

    def invert(self) -> Matrix4x4:
        m = self.values
        inv = [0.0] * 16
        inv[0] = (
            m[5] * m[10] * m[15]
            - m[5] * m[11] * m[14]
            - m[9] * m[6] * m[15]
            + m[9] * m[7] * m[14]
            + m[13] * m[6] * m[11]
            - m[13] * m[7] * m[10]
        )

        inv[4] = (
            -m[4] * m[10] * m[15]
            + m[4] * m[11] * m[14]
            + m[8] * m[6] * m[15]
            - m[8] * m[7] * m[14]
            - m[12] * m[6] * m[11]
            + m[12] * m[7] * m[10]
        )

        inv[8] = (
            m[4] * m[9] * m[15]
            - m[4] * m[11] * m[13]
            - m[8] * m[5] * m[15]
            + m[8] * m[7] * m[13]
            + m[12] * m[5] * m[11]
            - m[12] * m[7] * m[9]
        )

        inv[12] = (
            -m[4] * m[9] * m[14]
            + m[4] * m[10] * m[13]
            + m[8] * m[5] * m[14]
            - m[8] * m[6] * m[13]
            - m[12] * m[5] * m[10]
            + m[12] * m[6] * m[9]
        )

        inv[1] = (
            -m[1] * m[10] * m[15]
            + m[1] * m[11] * m[14]
            + m[9] * m[2] * m[15]
            - m[9] * m[3] * m[14]
            - m[13] * m[2] * m[11]
            + m[13] * m[3] * m[10]
        )

        inv[5] = (
            m[0] * m[10] * m[15]
            - m[0] * m[11] * m[14]
            - m[8] * m[2] * m[15]
            + m[8] * m[3] * m[14]
            + m[12] * m[2] * m[11]
            - m[12] * m[3] * m[10]
        )

        inv[9] = (
            -m[0] * m[9] * m[15]
            + m[0] * m[11] * m[13]
            + m[8] * m[1] * m[15]
            - m[8] * m[3] * m[13]
            - m[12] * m[1] * m[11]
            + m[12] * m[3] * m[9]
        )

        inv[13] = (
            m[0] * m[9] * m[14]
            - m[0] * m[10] * m[13]
            - m[8] * m[1] * m[14]
            + m[8] * m[2] * m[13]
            + m[12] * m[1] * m[10]
            - m[12] * m[2] * m[9]
        )

        inv[2] = (
            m[1] * m[6] * m[15]
            - m[1] * m[7] * m[14]
            - m[5] * m[2] * m[15]
            + m[5] * m[3] * m[14]
            + m[13] * m[2] * m[7]
            - m[13] * m[3] * m[6]
        )

        inv[6] = (
            -m[0] * m[6] * m[15]
            + m[0] * m[7] * m[14]
            + m[4] * m[2] * m[15]
            - m[4] * m[3] * m[14]
            - m[12] * m[2] * m[7]
            + m[12] * m[3] * m[6]
        )

        inv[10] = (
            m[0] * m[5] * m[15]
            - m[0] * m[7] * m[13]
            - m[4] * m[1] * m[15]
            + m[4] * m[3] * m[13]
            + m[12] * m[1] * m[7]
            - m[12] * m[3] * m[5]
        )

        inv[14] = (
            -m[0] * m[5] * m[14]
            + m[0] * m[6] * m[13]
            + m[4] * m[1] * m[14]
            - m[4] * m[2] * m[13]
            - m[12] * m[1] * m[6]
            + m[12] * m[2] * m[5]
        )

        inv[3] = (
            -m[1] * m[6] * m[11]
            + m[1] * m[7] * m[10]
            + m[5] * m[2] * m[11]
            - m[5] * m[3] * m[10]
            - m[9] * m[2] * m[7]
            + m[9] * m[3] * m[6]
        )

        inv[7] = (
            m[0] * m[6] * m[11]
            - m[0] * m[7] * m[10]
            - m[4] * m[2] * m[11]
            + m[4] * m[3] * m[10]
            + m[8] * m[2] * m[7]
            - m[8] * m[3] * m[6]
        )

        inv[11] = (
            -m[0] * m[5] * m[11]
            + m[0] * m[7] * m[9]
            + m[4] * m[1] * m[11]
            - m[4] * m[3] * m[9]
            - m[8] * m[1] * m[7]
            + m[8] * m[3] * m[5]
        )

        inv[15] = (
            m[0] * m[5] * m[10]
            - m[0] * m[6] * m[9]
            - m[4] * m[1] * m[10]
            + m[4] * m[2] * m[9]
            + m[8] * m[1] * m[6]
            - m[8] * m[2] * m[5]
        )

        det = m[0] * inv[0] + m[1] * inv[4] + m[2] * inv[8] + m[3] * inv[12]

        if det == 0:
            raise ValueError("matrix not invertible")

        det = 1.0 / det
        inv = [v * det for v in inv]

        return Matrix4x4(tuple(inv))


class Quaternion(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("z", ctypes.c_float),
        ("w", ctypes.c_float),
    ]

    def __init__(
        self, x: float = 0.0, y: float = 0.0, z: float = 0.0, w: float = 1.0
    ) -> None:
        super().__init__(x, y, z, w)

    @classmethod
    def identity(cls) -> Quaternion:
        return cls(0.0, 0.0, 0.0, 1.0)

    @classmethod
    def from_axis_angle(cls, axis: Vector3, angle: float) -> Quaternion:
        half = angle / 2
        s = math.sin(half)
        return cls(axis.x * s, axis.y * s, axis.z * s, math.cos(half))

    def __add__(self, other: Quaternion) -> Quaternion:
        return Quaternion(
            self.x + other.x, self.y + other.y, self.z + other.z, self.w + other.w
        )

    def __sub__(self, other: Quaternion) -> Quaternion:
        return Quaternion(
            self.x - other.x, self.y - other.y, self.z - other.z, self.w - other.w
        )

    @overload
    def __mul__(self, other: Quaternion) -> Quaternion: ...
    @overload
    def __mul__(self, other: float) -> Quaternion: ...

    def __mul__(self, other: Union[Quaternion, float]) -> Quaternion:
        if isinstance(other, Quaternion):
            return self._mul_quat(other)

        if isinstance(other, (int, float)):
            return Quaternion(
                self.x * other, self.y * other, self.z * other, self.w * other
            )

        raise NotImplementedError()

    def __rmul__(self, s: float) -> Quaternion:
        return Quaternion(self.x * s, self.y * s, self.z * s, self.w * s)

    def _mul_quat(self, b: Quaternion) -> Quaternion:
        a = self

        # fmt: off
        return Quaternion(
            a.x * b.w + a.w * b.x + a.y * b.z - a.z * b.y,
            a.y * b.w + a.w * b.y + a.z * b.x - a.x * b.z,
            a.z * b.w + a.w * b.z + a.x * b.y - a.y * b.x,
            a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
        )
        # fmt: on

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y
        yield self.z
        yield self.w

    def __repr__(self) -> str:
        return f"Quaternion({self.x:.3f}, {self.y:.3f}, {self.z:.3f}, {self.w:.3f})"

    def norm(self) -> float:
        return math.sqrt(self.x**2 + self.y**2 + self.z**2 + self.w**2)

    def normalize(self) -> Quaternion:
        n = self.norm()
        return Quaternion(self.x / n, self.y / n, self.z / n, self.w / n)

    def conjugate(self) -> Quaternion:
        return Quaternion(-self.x, -self.y, -self.z, self.w)

    def invert(self) -> Quaternion:
        d = self.x**2 + self.y**2 + self.z**2 + self.w**2
        inv_d = 1.0 / d if d else 0.0
        return Quaternion(
            -self.x * inv_d, -self.y * inv_d, -self.z * inv_d, self.w * inv_d
        )

    def lerp(self, other: Quaternion, t: float) -> Quaternion:
        return Quaternion(
            self.x + (other.x - self.x) * t,
            self.y + (other.y - self.y) * t,
            self.z + (other.z - self.z) * t,
            self.w + (other.w - self.w) * t,
        )

    def slerp(self, other: Quaternion, t: float) -> Quaternion:
        ax, ay, az, aw = self.x, self.y, self.z, self.w
        bx, by, bz, bw = other.x, other.y, other.z, other.w

        dot = ax * bx + ay * by + az * bz + aw * bw
        if dot < 0:
            bx, by, bz, bw = -bx, -by, -bz, -bw
            dot = -dot

        omega = math.acos(max(-1.0, min(1.0, dot)))
        if omega == 0.0:
            return other

        sin_omega = math.sin(omega)
        s1 = math.sin((1.0 - t) * omega) / sin_omega
        s2 = math.sin(t * omega) / sin_omega

        return Quaternion(
            s1 * ax + s2 * bx,
            s1 * ay + s2 * by,
            s1 * az + s2 * bz,
            s1 * aw + s2 * bw,
        )

    def to_matrix(self) -> Matrix4x4:
        x, y, z, w = self.x, self.y, self.z, self.w
        xx, yx, yy = x * x * 2, y * x * 2, y * y * 2
        zx, zy, zz = z * x * 2, z * y * 2, z * z * 2
        wx, wy, wz = w * x * 2, w * y * 2, w * z * 2

        # fmt: off
        return Matrix4x4((
            1 - yy - zz, yx - wz, zx + wy, 0,
            yx + wz, 1 - xx - zz, zy - wx, 0,
            zx - wy, zy + wx, 1 - xx - yy, 0,
            0, 0, 0, 1,
        ))
        # fmt: on

    @classmethod
    def from_matrix(cls, m: Matrix4x4) -> Quaternion:
        v = m.values
        m00, m01, m02 = v[0], v[1], v[2]
        m10, m11, m12 = v[4], v[5], v[6]
        m20, m21, m22 = v[8], v[9], v[10]

        trace = m00 + m11 + m22

        if trace > 0:
            s = 0.5 / math.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (m21 - m12) * s
            y = (m02 - m20) * s
            z = (m10 - m01) * s
        elif m00 > m11 and m00 > m22:
            s = 2.0 * math.sqrt(1.0 + m00 - m11 - m22)
            w = (m21 - m12) / s
            x = 0.25 * s
            y = (m01 + m10) / s
            z = (m02 + m20) / s
        elif m11 > m22:
            s = 2.0 * math.sqrt(1.0 + m11 - m00 - m22)
            w = (m02 - m20) / s
            x = (m01 + m10) / s
            y = 0.25 * s
            z = (m12 + m21) / s
        else:
            s = 2.0 * math.sqrt(1.0 + m22 - m00 - m11)
            w = (m10 - m01) / s
            x = (m02 + m20) / s
            y = (m12 + m21) / s
            z = 0.25 * s

        return cls(x, y, z, w)


class PssgScalarDataType(Enum):
    FLOAT = ("f", 4)
    CHAR = ("b", 1)
    SHORT = ("h", 2)
    INT = ("i", 4)
    UCHAR = ("B", 1)
    USHORT = ("H", 2)
    UINT = ("I", 4)


class PssgArrayBufferType(Enum):
    FLOAT = (PssgScalarDataType.FLOAT, 1)
    FLOAT2 = (PssgScalarDataType.FLOAT, 2)
    FLOAT3 = (PssgScalarDataType.FLOAT, 3)
    FLOAT4 = (PssgScalarDataType.FLOAT, 4)
    CHAR = (PssgScalarDataType.CHAR, 1)
    CHAR2 = (PssgScalarDataType.CHAR, 2)
    CHAR3 = (PssgScalarDataType.CHAR, 3)
    CHAR4 = (PssgScalarDataType.CHAR, 4)
    SHORT = (PssgScalarDataType.SHORT, 1)
    SHORT2 = (PssgScalarDataType.SHORT, 2)
    SHORT3 = (PssgScalarDataType.SHORT, 3)
    SHORT4 = (PssgScalarDataType.SHORT, 4)
    INT = (PssgScalarDataType.INT, 1)
    INT2 = (PssgScalarDataType.INT, 2)
    INT3 = (PssgScalarDataType.INT, 3)
    INT4 = (PssgScalarDataType.INT, 4)
    UCHAR = (PssgScalarDataType.UCHAR, 1)
    UCHAR2 = (PssgScalarDataType.UCHAR, 2)
    UCHAR3 = (PssgScalarDataType.UCHAR, 3)
    UCHAR4 = (PssgScalarDataType.UCHAR, 4)
    USHORT = (PssgScalarDataType.USHORT, 1)
    USHORT2 = (PssgScalarDataType.USHORT, 2)
    USHORT3 = (PssgScalarDataType.USHORT, 3)
    USHORT4 = (PssgScalarDataType.USHORT, 4)
    UINT = (PssgScalarDataType.UINT, 1)
    UINT2 = (PssgScalarDataType.UINT, 2)
    UINT3 = (PssgScalarDataType.UINT, 3)
    UINT4 = (PssgScalarDataType.UINT, 4)


PSSG_KNOWN_ARRAY_TYPES = {
    "float": PssgArrayBufferType.FLOAT,
    "float2": PssgArrayBufferType.FLOAT2,
    "float3": PssgArrayBufferType.FLOAT3,
    "float4": PssgArrayBufferType.FLOAT4,
    "uchar": PssgArrayBufferType.UCHAR,
    "uchar2": PssgArrayBufferType.UCHAR2,
    "uchar3": PssgArrayBufferType.UCHAR3,
    "uchar4": PssgArrayBufferType.UCHAR4,
    "ushort": PssgArrayBufferType.USHORT,
    "ushort2": PssgArrayBufferType.USHORT2,
    "ushort3": PssgArrayBufferType.USHORT3,
    "ushort4": PssgArrayBufferType.USHORT4,
}


def pssg_transmute_buffer(
    src_data: bytearray,
    src_type: PssgArrayBufferType,
    src_stride: int,
    src_offset: int,
    dst_data: bytearray,
    dst_type: PssgArrayBufferType,
    dst_offset: int,
    dst_stride: int,
    count: int,
    src_endian: str = ">",  # ps3 source data is big endian
    dst_endian: str = "<",  # assume little endian destination
):
    def _is_integer_type(st: PssgScalarDataType) -> bool:
        return st in (
            PssgScalarDataType.INT,
            PssgScalarDataType.UINT,
            PssgScalarDataType.SHORT,
            PssgScalarDataType.USHORT,
            PssgScalarDataType.CHAR,
            PssgScalarDataType.UCHAR,
        )

    def _is_unsigned_type(st: PssgScalarDataType) -> bool:
        return st in (
            PssgScalarDataType.UINT,
            PssgScalarDataType.USHORT,
            PssgScalarDataType.UCHAR,
        )

    def _is_float_type(st: PssgScalarDataType) -> bool:
        return st == PssgScalarDataType.FLOAT

    def _convert_scalar(
        value, src_base_type: PssgScalarDataType, dst_base_type: PssgScalarDataType
    ):
        # same type is noop
        if src_base_type == dst_base_type:
            return value

        # float to int use round()
        if _is_float_type(src_base_type) and _is_integer_type(dst_base_type):
            v = round(value)
            return max(0, v) if _is_unsigned_type(dst_base_type) else v

        # int to float use casting
        if _is_integer_type(src_base_type) and _is_float_type(dst_base_type):
            return float(value)

        # widen integers
        if _is_integer_type(src_base_type) and _is_integer_type(dst_base_type):
            return int(value)

        raise NotImplementedError(
            f"No conversion rule from {src_base_type.value} to {dst_base_type.value}"
        )

    src_scalar_type, src_components = src_type.value
    src_code, src_byte_width = src_scalar_type.value

    dst_scalar_type, dst_components = dst_type.value
    dst_code, dst_byte_width = dst_scalar_type.value

    pad_value = 0.0 if _is_float_type(src_scalar_type) else 0

    if src_stride == 0:
        src_stride = src_byte_width * src_components

    if dst_stride == 0:
        dst_stride = dst_byte_width * dst_components

    for i in range(count):
        src_ptr = src_offset + i * src_stride
        dst_ptr = dst_offset + i * dst_stride

        src_values = list(
            struct.unpack_from(
                f"{src_endian}{src_components}{src_code}", src_data, src_ptr
            )
        )

        if dst_components > src_components:
            src_values = src_values + [pad_value] * (dst_components - len(src_values))
        elif dst_components < len(src_values):
            src_values = src_values[:dst_components]

        dst_values = [
            _convert_scalar(v, src_scalar_type, dst_scalar_type) for v in src_values
        ]

        struct.pack_into(
            f"{dst_endian}{dst_components}{dst_code}", dst_data, dst_ptr, *dst_values
        )


class PssgModelTree:
    @dataclass
    class PssgModelNode:
        id: str

        bind_translation: Vector3 = Vector3.zero()
        bind_scale: Vector3 = Vector3(1, 1, 1)
        bind_rotation: Quaternion = Quaternion.identity()
        bind_transform: Matrix4x4 = Matrix4x4.identity()

        translation: Vector3 = Vector3.zero()
        scale: Vector3 = Vector3(1, 1, 1)
        rotation: Quaternion = Quaternion.identity()

        local_matrix: Matrix4x4 = Matrix4x4.identity()
        model_matrix: Matrix4x4 = Matrix4x4.identity()

        bounding_min: Vector3 = Vector3.zero()
        bounding_max: Vector3 = Vector3.zero()

        children: list[PssgModelTree.PssgModelNode] = field(default_factory=list)

    @dataclass
    class PssgModelRenderNode(PssgModelNode):
        vertex_buffer: bytearray = field(default_factory=bytearray)
        index_buffer: bytearray = field(default_factory=bytearray)
        num_vertices: int = 0
        num_indices: int = 0
        texture: Optional[PssgDecodedTexture] = None

    class PssgSkinJoint(NamedTuple):
        joint_id: str
        inverse_bind: Matrix4x4

    @dataclass
    class PssgModelSkinnedNode(PssgModelRenderNode):
        skin_joints: list[PssgModelTree.PssgSkinJoint] = field(default_factory=list)

    NODE_TYPES = ["NODE", "ROOTNODE", "RENDERNODE", "SKINNODE", "JOINTNODE"]

    pssg_libraries: list[PssgElement] = []
    pssg_model: PssgElement
    pssg_buffer_library: PssgElement
    pssg_source_library: PssgElement
    pssg_material_library: PssgElement
    pssg_node_library: PssgElement
    pssg_skeleton_library: PssgElement
    pssg_shader_library: PssgElement

    root: PssgModelNode
    textures: dict[str, PssgDecodedTexture] = {}
    rendernodes: dict[str, PssgModelRenderNode] = {}
    skinnednodes: dict[str, PssgModelSkinnedNode] = {}
    jointnodes: dict[str, PssgModelNode] = {}

    def __init__(self, element: PssgElement):
        if element.name != "PSSGDATABASE":
            raise Exception(f"expected pssg PSSGDATABASE element, got {element.type}")

        self.pssg_model = element

        """
        pssg files have "libraries", they basically are like file sections dedicated
        to different things to be put there

        ``RENDERINTERFACEBOUND`` - this is basically raw (typed) buffer data, e.g. it
        may hold float3 data for positions and normals, or dxt1 compressed texels

        ``SHADERINSTANCE`` - as the name suggests, instances of shaders, basically
        the important part for us are the shader inputs defined in this section as 
        this is how textures are bound to meshes

        ``RENDERDATASOURCE`` - defines "streams", basically this is very similar to 
        gltf accessors more or less, of course it is also overcomplicated

        ``NODE`` - scene nodes, basically what you would expect, a hierarchy of
        different kinds of nodes
        """

        self.pssg_buffer_library = self._find_library("RENDERINTERFACEBOUND")
        self.pssg_source_library = self._find_library("RENDERDATASOURCE")
        self.pssg_node_library = self._find_library("NODE")
        self.pssg_material_library = self._find_library("SHADERINSTANCE")
        self.pssg_skeleton_library = self._find_library("SKELETON")
        self.pssg_shader_library = self._find_library("SHADERGROUP")

        pssg_root = self.pssg_node_library.find_child("ROOTNODE")
        if pssg_root is None:
            raise Exception("ROOTNODE was not found in the node library")

        self.root = self._parse_pssg_node(pssg_root)
        self.compute_transforms()

    def iter_nodes(self) -> Iterator[PssgModelTree.PssgModelNode]:
        def _recurse_model_node(node: PssgModelTree.PssgModelNode):
            yield node

            for child in node.children:
                yield from _recurse_model_node(child)

        yield from _recurse_model_node(self.root)

    def compute_transforms(self):
        def _recurse_model_node(node: PssgModelTree.PssgModelNode, world: Matrix4x4):
            # T * R * S
            node.local_matrix = (
                Matrix4x4.translation(node.translation)
                * node.rotation.to_matrix()
                * Matrix4x4.scale(node.scale)
            )
            node.model_matrix = world * node.local_matrix

            for child in node.children:
                _recurse_model_node(child, world)

        _recurse_model_node(self.root, Matrix4x4.identity())

    def _parse_pssg_node(self, node: PssgElement) -> PssgModelNode:
        """
        there are different types of nodes here to parse

        ``ROOTNODE`` - there should be only one, the first one
        ``NODE`` - just a regular named node with transform, bbox etc
        ``RENDERNODE`` - this node has something to be rendered
        ``SKINNODE`` - this is a skinned mesh node, it uses some complex pssg modifier
        networks, but we really don't care about this, we just want the raw input data
        for the skinning since it is exactly as one would expect a skinned mesh to be
        ``JOINTNODE`` - transform only node that will be used as a joint by some skinned
        mesh

        we have to decide here, what kind of node this is and how to parse it
        """

        match node.name:
            case "NODE" | "ROOTNODE" | "JOINTNODE":
                return self._parse_pssg_regular_node(node)

            case "RENDERNODE":
                return self._parse_pssg_render_node(node)

            case "SKINNODE":
                return self._parse_pssg_skin_node(node)

            case _:
                raise Exception(f"unknown node type {node.name}")

    def _parse_pssg_node_base(
        self, node: PssgElement, child: PssgElement, result: PssgModelNode
    ) -> bool:
        if child.name in self.NODE_TYPES:
            result.children.append(self._parse_pssg_node(child))
            return True
        elif child.name == "TRANSFORM":
            transform_matrix = Matrix4x4(child.value)
            translation, rotation, scale = transform_matrix.decompose()

            result.bind_translation = translation
            result.bind_rotation = rotation
            result.bind_scale = scale
            result.bind_transform = transform_matrix

            result.translation = translation
            result.rotation = rotation
            result.scale = scale
            result.local_matrix = transform_matrix

            return True
        elif child.name == "BOUNDINGBOX":
            result.bounding_min = Vector3(
                child.value[0], child.value[1], child.value[2]
            )
            result.bounding_max = Vector3(
                child.value[3], child.value[4], child.value[5]
            )
            return True

        return False

    def _parse_pssg_regular_node(self, node: PssgElement) -> PssgModelNode:
        node_id = node.get_attribute("id").value
        result = self.PssgModelNode(id=node_id)

        for child in node.children:
            if not self._parse_pssg_node_base(node, child, result):
                logging.warning("unhandled node type %s", child.name)

        if node.name == "JOINTNODE":
            self.jointnodes[node_id] = result

        return result

    def _find_pssg_render_data_source(self, id: str) -> Optional[PssgElement]:
        for child in self.pssg_source_library.children:
            if child.name != "RENDERDATASOURCE":
                pass

            data_source_id = str(child.get_attribute("id").value)
            if data_source_id == id:
                return child

        return None

    def _find_pssg_shader_instance(self, id: str) -> Optional[PssgElement]:
        for child in self.pssg_material_library.children:
            if child.name != "SHADERINSTANCE":
                pass

            shader_instance_id = str(child.get_attribute("id").value)
            if shader_instance_id == id:
                return child

        return None

    def _find_pssg_data_block(self, id: str) -> Optional[PssgElement]:
        for child in self.pssg_buffer_library.children:
            if child.name != "DATABLOCK":
                pass

            data_block_id = str(child.get_attribute("id").value)
            if data_block_id == id:
                return child

        return None

    def _find_pssg_texture(self, id: str) -> Optional[PssgElement]:
        textures = self.pssg_buffer_library.find_children("TEXTURE")
        for texture in textures:
            texture_id = texture.find_attribute("id")
            if texture_id is None:
                continue

            if texture_id.value == id:
                return texture

    def _find_pssg_shader_group(self, id: str) -> Optional[PssgElement]:
        shader_groups = self.pssg_shader_library.find_children("SHADERGROUP")
        for shader_group in shader_groups:
            shader_group_id = shader_group.find_attribute("id")
            if shader_group_id is None:
                continue

            if shader_group_id.value == id:
                return shader_group

    def _parse_pssg_shader_instance(
        self, node: PssgModelRenderNode, shader_instance: PssgElement
    ):
        # apply texture using shader instance input data
        shader_inputs = shader_instance.find_children("SHADERINPUT")
        for shader_input in shader_inputs:
            input_type = shader_input.get_attribute("type").value
            if input_type != "texture":
                pass

            texture_id = shader_input.get_attribute("texture").value.lstrip("#")
            texture = self._find_pssg_texture(texture_id)

            if texture is None:
                raise Exception(f"missing texture {texture_id}")

            if texture_id not in self.textures:
                self.textures[texture_id] = PssgDecodedTexture(texture)

            node.texture = self.textures[texture_id]

        if node.texture is not None:
            return

        # texture still not bound, so search shader defaults instead
        shader_group_id = shader_instance.find_attribute("shaderGroup")
        if shader_group_id is None:
            return

        shader_group = self._find_pssg_shader_group(shader_group_id.value)
        if shader_group is None:
            return

        shader_inputs = shader_group.find_children("SHADERINPUT")
        for shader_input in shader_inputs:
            shader_input_type = shader_input.get_attribute("type").value
            if shader_input_type == "texture":
                texture_id = shader_input.get_attribute("texture").value.lstrip("#")
                texture = self._find_pssg_texture(texture_id)

                if texture is None:
                    raise Exception(f"missing texture {texture_id}")

                if texture_id not in self.textures:
                    self.textures[texture_id] = PssgDecodedTexture(texture)

                node.texture = self.textures[texture_id]

    def _parse_pssg_render_data_source(
        self, node: PssgModelRenderNode, render_data_source: PssgElement
    ):
        render_data_source_id = render_data_source.get_attribute("id").value
        render_idx_source = render_data_source.find_child("RENDERINDEXSOURCE")
        if render_idx_source is None:
            raise Exception(
                f"render data source {render_data_source_id} does not provide indices"
            )

        render_indices = render_idx_source.find_child("INDEXSOURCEDATA")
        if render_indices is None:
            raise Exception(
                f"invalid format for render index source in {render_data_source_id}"
            )

        indices = render_indices.value
        indices_format = str(render_idx_source.get_attribute("format").value)
        indices_count = int(render_idx_source.get_attribute("count").value)

        logging.debug("found index buffer of size %d", len(indices))

        # construct the vertex buffer out of streams
        render_streams = render_data_source.find_children("RENDERSTREAM")

        FLOAT_SIZE = ctypes.sizeof(ctypes.c_float)
        UINT_SIZE = ctypes.sizeof(ctypes.c_uint32)
        VERTEX_STRIDE = FLOAT_SIZE * 15 + UINT_SIZE * 4
        POS_OFFSET = FLOAT_SIZE * 0
        UV_OFFSET = FLOAT_SIZE * 3
        COLOR_OFFSET = FLOAT_SIZE * 5
        NORMAL_OFFSET = FLOAT_SIZE * 8
        SKINWEIGHT_OFFSET = FLOAT_SIZE * 11
        SKINJOINT_OFFSET = FLOAT_SIZE * 15

        LAYOUT_PER_RENDER_TYPE = {
            "Vertex": (POS_OFFSET, PssgArrayBufferType.FLOAT3),
            "ST": (UV_OFFSET, PssgArrayBufferType.FLOAT2),
            "Normal": (NORMAL_OFFSET, PssgArrayBufferType.FLOAT3),
            "SkinnableVertex": (POS_OFFSET, PssgArrayBufferType.FLOAT3),
            "SkinnableNormal": (NORMAL_OFFSET, PssgArrayBufferType.FLOAT3),
            "SkinWeights": (SKINWEIGHT_OFFSET, PssgArrayBufferType.FLOAT4),
            "SkinIndices": (SKINJOINT_OFFSET, PssgArrayBufferType.UINT4),
        }

        vertex_buffer = bytearray()
        num_vertices = -1

        for render_stream in render_streams:
            data_block_name = render_stream.get_attribute("dataBlock").value.lstrip("#")
            data_block_src = self._find_pssg_data_block(data_block_name)
            if data_block_src is None:
                raise Exception(f"data block {data_block_name} does not exist")

            # data blocks are "typed", thats how we know what vertex attribute this data
            # block is bound to
            data_block_name = data_block_src.get_attribute("id").value
            data_block_element_count = int(
                data_block_src.get_attribute("elementCount").value
            )

            if num_vertices == -1:
                vertex_buffer = bytearray(data_block_element_count * VERTEX_STRIDE)
                num_vertices = data_block_element_count

            data_block_stream = data_block_src.find_child("DATABLOCKSTREAM")
            if data_block_stream is None:
                raise Exception(
                    f"data block {data_block_name} does not have any DATABLOCKSTREAM"
                )

            data_block_data = data_block_src.find_child("DATABLOCKDATA")
            if data_block_data is None:
                raise Exception(
                    f"data block {data_block_name} does not have any DATABLOCKDATA"
                )

            data_block_render_type = str(
                data_block_stream.get_attribute("renderType").value
            )  # Vertex, Normal, ST
            data_block_data_type = str(
                data_block_stream.get_attribute("dataType").value
            )  # float3 etc
            data_block_offset = int(
                data_block_stream.get_attribute("offset").value
            )  # in bytes
            data_block_stride = int(
                data_block_stream.get_attribute("stride").value
            )  # in bytes

            if data_block_render_type not in LAYOUT_PER_RENDER_TYPE:
                logging.warning("unsupported render type %s", data_block_render_type)
                continue

            src_type = PSSG_KNOWN_ARRAY_TYPES[data_block_data_type]
            src_offset = data_block_offset
            src_stride = data_block_stride
            dst_offset, dst_type = LAYOUT_PER_RENDER_TYPE[data_block_render_type]

            pssg_transmute_buffer(
                src_data=data_block_data.value,
                src_type=src_type,
                src_stride=src_stride,
                src_offset=src_offset,
                dst_data=vertex_buffer,
                dst_type=dst_type,
                dst_stride=VERTEX_STRIDE,
                dst_offset=dst_offset,
                count=data_block_element_count,
            )

        # fill with color white
        for i in range(num_vertices):
            struct.pack_into(
                "<3f", vertex_buffer, i * VERTEX_STRIDE + COLOR_OFFSET, 1.0, 1.0, 1.0
            )

        node.vertex_buffer = vertex_buffer
        node.num_vertices = num_vertices
        node.index_buffer = bytearray(UINT_SIZE * indices_count)
        node.num_indices = indices_count

        pssg_transmute_buffer(
            src_data=indices,
            src_type=PSSG_KNOWN_ARRAY_TYPES[indices_format],
            src_stride=0,
            src_offset=0,
            dst_data=node.index_buffer,
            dst_type=PssgArrayBufferType.UINT,
            dst_stride=4,
            dst_offset=0,
            count=indices_count,
        )

    def _parse_pssg_render_stream_instance(
        self, node: PssgModelRenderNode, element: PssgElement
    ):
        """
        simple explaination of different nodes found in this place

        ``RISTREAM`` sets an alias "id" to "stream"
        ``RENDERINSTANCESOURCE`` links this to a ``RENDERDATASOURCE`` node
        ``RENDERINSTANCESTREAM`` binds the stream, aliased by ``RISTREAM``
        """

        shader_instance_id = element.get_attribute("shader")
        stream_count = int(element.get_attribute("streamCount").value)
        index_source = str(element.get_attribute("indices").value)
        source_count = int(element.get_attribute("sourceCount").value)

        if source_count != 1:
            raise Exception(f"source count is {source_count}, expected 1")

        instance_source: Optional[str] = None

        for child in element.children:
            match child.name:
                case "RENDERINSTANCESOURCE":
                    source = str(child.get_attribute("source").value)
                    instance_source = source

        if instance_source is None:
            raise Exception("no instance source was specified")

        render_data_source = self._find_pssg_render_data_source(
            instance_source.lstrip("#")
        )
        if render_data_source is None:
            raise Exception(f"render data source {instance_source} does not exist")

        shader_instance = self._find_pssg_shader_instance(
            shader_instance_id.value.lstrip("#")
        )
        if shader_instance is None:
            raise Exception(
                f"shader instance {shader_instance_id.value} does not exist"
            )

        self._parse_pssg_shader_instance(node, shader_instance)
        self._parse_pssg_render_data_source(node, render_data_source)

    def _parse_pssg_render_node(self, node: PssgElement) -> PssgModelNode:
        node_id = node.get_attribute("id").value
        result = self.PssgModelRenderNode(id=node_id)

        for child in node.children:
            if not self._parse_pssg_node_base(node, child, result):
                if child.name == "RENDERSTREAMINSTANCE":
                    self._parse_pssg_render_stream_instance(result, child)
                else:
                    logging.warning("unhandled node type %s", child.name)

        self.rendernodes[result.id] = result
        return result

    def _parse_pssg_skin_node(self, node: PssgElement) -> PssgModelNode:
        node_id = node.get_attribute("id").value
        result = self.PssgModelSkinnedNode(id=node_id)

        for child in node.children:
            if self._parse_pssg_node_base(node, child, result):
                continue

            match child.name:
                case "MODIFIERNETWORKINSTANCE" | "SKINJOINT":
                    continue

                case _:
                    logging.warning("unhandled node type %s", child.name)

        # skinned draw nodes are some kind of modifier around regular buffers
        # we really don't care about parsing them properly, whats important
        # is the data they hold
        network_instance = node.find_child("MODIFIERNETWORKINSTANCE")
        if network_instance is None:
            raise Exception(f"skin node {node_id} is missing MODIFIERNETWORKINSTANCE")

        render_instance_source = network_instance.find_child("RENDERINSTANCESOURCE")
        if render_instance_source is None:
            raise Exception(f"skin node {node_id} is missing RENDERINSTANCESOURCE")

        shader_instance_id: str = network_instance.get_attribute("shader").value
        render_data_src_id: str = render_instance_source.get_attribute("source").value

        render_data_source = self._find_pssg_render_data_source(
            render_data_src_id.lstrip("#")
        )
        if render_data_source is None:
            raise Exception(f"render data source {render_data_src_id} does not exist")

        shader_instance = self._find_pssg_shader_instance(
            shader_instance_id.lstrip("#")
        )
        if shader_instance is None:
            raise Exception(f"shader instance {shader_instance_id} does not exist")

        self._parse_pssg_shader_instance(result, shader_instance)
        self._parse_pssg_render_data_source(result, render_data_source)

        # TODO parse skin

        self.rendernodes[result.id] = result
        self.skinnednodes[result.id] = result
        return result

    def _find_library(self, type: str) -> PssgElement:
        if len(self.pssg_libraries) == 0:
            self.pssg_libraries = self.pssg_model.find_children("LIBRARY")

        for library in self.pssg_libraries:
            library_type = library.find_attribute("type")
            if library_type is None:
                continue

            if library_type.value == type:
                return library

        raise Exception(f"cannot find a pssg library of type {type}")


VERTEX_SHADER = """#version 400

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec2 a_uv;
layout(location = 2) in vec3 a_color;
layout(location = 3) in vec3 a_normal;

uniform mat4 u_projection;
uniform mat4 u_view;
uniform mat4 u_world;

out VS_OUT {
    vec2 uv;
    vec3 color;
    vec3 normal;
} vs_out;

void main() {
    vs_out.uv = a_uv;
    vs_out.color = a_color;
    vs_out.normal = (u_world * vec4(a_normal, 0.0)).xyz;
    gl_Position = u_projection * u_view * u_world * vec4(a_position, 1.0);
}
"""

FRAGMENT_SHADER = """#version 400

in VS_OUT {
    vec2 uv;
    vec3 color;
    vec3 normal;
} fs_in;

uniform vec4 u_color;

uniform sampler2D u_diffuse;
uniform bool u_use_diffuse;

out vec4 frag_color;

void main() {
    vec4 map_color = vec4(1.0, 1.0, 1.0, 1.0);
    if (u_use_diffuse) {
        map_color = texture(u_diffuse, fs_in.uv).rgba;
    }

    vec3 color = map_color.rgb * fs_in.color;
    frag_color = vec4(color.rgb, map_color.a) * u_color;
}
"""

# fmt: off
CUBE_VERTICES = [
    # Front (+Z) - red
    -1.0, -1.0,  1.0, 0.0, 0.0, 1.0, 0.0, 0.0,  0.0, 0.0, 1.0,
     1.0, -1.0,  1.0, 1.0, 0.0, 1.0, 0.0, 0.0,  0.0, 0.0, 1.0,
     1.0,  1.0,  1.0, 1.0, 1.0, 1.0, 0.0, 0.0,  0.0, 0.0, 1.0,
    -1.0,  1.0,  1.0, 0.0, 1.0, 1.0, 0.0, 0.0,  0.0, 0.0, 1.0,

    # Back (-Z) - green
     1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 1.0, 0.0,  0.0, 0.0, -1.0,
    -1.0, -1.0, -1.0, 1.0, 0.0, 0.0, 1.0, 0.0,  0.0, 0.0, -1.0,
    -1.0,  1.0, -1.0, 1.0, 1.0, 0.0, 1.0, 0.0,  0.0, 0.0, -1.0,
     1.0,  1.0, -1.0, 0.0, 1.0, 0.0, 1.0, 0.0,  0.0, 0.0, -1.0,

    # Left (-X) - blue
    -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0, -1.0, 0.0, 0.0,
    -1.0, -1.0,  1.0, 1.0, 0.0, 0.0, 0.0, 1.0, -1.0, 0.0, 0.0,
    -1.0,  1.0,  1.0, 1.0, 1.0, 0.0, 0.0, 1.0, -1.0, 0.0, 0.0,
    -1.0,  1.0, -1.0, 0.0, 1.0, 0.0, 0.0, 1.0, -1.0, 0.0, 0.0,

    # Right (+X) - yellow
     1.0, -1.0,  1.0, 0.0, 0.0, 1.0, 1.0, 0.0,  1.0, 0.0, 0.0,
     1.0, -1.0, -1.0, 1.0, 0.0, 1.0, 1.0, 0.0,  1.0, 0.0, 0.0,
     1.0,  1.0, -1.0, 1.0, 1.0, 1.0, 1.0, 0.0,  1.0, 0.0, 0.0,
     1.0,  1.0,  1.0, 0.0, 1.0, 1.0, 1.0, 0.0,  1.0, 0.0, 0.0,

    # Top (+Y) - magenta
    -1.0,  1.0,  1.0, 0.0, 0.0, 1.0, 0.0, 1.0,  0.0, 1.0, 0.0,
     1.0,  1.0,  1.0, 1.0, 0.0, 1.0, 0.0, 1.0,  0.0, 1.0, 0.0,
     1.0,  1.0, -1.0, 1.0, 1.0, 1.0, 0.0, 1.0,  0.0, 1.0, 0.0,
    -1.0,  1.0, -1.0, 0.0, 1.0, 1.0, 0.0, 1.0,  0.0, 1.0, 0.0,

    # Bottom (-Y) - cyan
    -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 1.0, 1.0,  0.0, -1.0, 0.0,
     1.0, -1.0, -1.0, 1.0, 0.0, 0.0, 1.0, 1.0,  0.0, -1.0, 0.0,
     1.0, -1.0,  1.0, 1.0, 1.0, 0.0, 1.0, 1.0,  0.0, -1.0, 0.0,
    -1.0, -1.0,  1.0, 0.0, 1.0, 0.0, 1.0, 1.0,  0.0, -1.0, 0.0,
]

CUBE_INDICES = [
     0,  1,  2,   2,  3,  0,   # Front
     4,  5,  6,   6,  7,  4,   # Back
     8,  9, 10,  10, 11,  8,   # Left
    12, 13, 14,  14, 15, 12,   # Right
    16, 17, 18,  18, 19, 16,   # Top
    20, 21, 22,  22, 23, 20,   # Bottom
]
# fmt: on


class PssgViewerFrame(wx.Frame):
    class SceneShader:
        @dataclass
        class Uniform:
            name: str
            size: int
            gl_type: int
            location: int

        vs_source: str
        fs_source: str

        def __init__(self, vs_source: str, fs_source: str):
            self.vs_source = vs_source
            self.fs_source = fs_source
            self.handle = None
            self.uniforms = {}

        def start(self):
            if self.handle is not None:
                raise Exception("shader program already started")

            vs = self._compile_shader(GL.GL_VERTEX_SHADER, self.vs_source)

            try:
                fs = self._compile_shader(GL.GL_FRAGMENT_SHADER, self.fs_source)
            except Exception as e:
                GL.glDeleteShader(vs)
                raise e

            self.handle = GL.glCreateProgram()
            GL.glAttachShader(self.handle, vs)
            GL.glAttachShader(self.handle, fs)
            GL.glLinkProgram(self.handle)

            link_status = GL.glGetProgramiv(self.handle, GL.GL_LINK_STATUS)
            link_error_log = None

            if not link_status:
                link_error_log = GL.glGetProgramInfoLog(self.handle)
                GL.glDeleteProgram(self.handle)
                self.handle = None

            GL.glDeleteShader(vs)
            GL.glDeleteShader(fs)

            if link_error_log:
                raise Exception(f"failed to link shader program: {link_error_log}")

            self._map_uniforms()

        def destroy(self):
            GL.glDeleteProgram(self.handle)
            self.handle = None

        def bind(self):
            GL.glUseProgram(self.handle)

        def set_flag(self, name: str, value: bool):
            GL.glUniform1i(self._get_typed_uniform_location(name, GL.GL_BOOL), value)

        def set_int(self, name: str, value: int):
            GL.glUniform1i(self._get_typed_uniform_location(name, GL.GL_INT), value)

        def set_float(self, name: str, value: float):
            GL.glUniform1f(self._get_typed_uniform_location(name, GL.GL_FLOAT), value)

        def set_vector2(self, name: str, value: tuple[float, float]):
            GL.glUniform2fv(
                self._get_typed_uniform_location(name, GL.GL_FLOAT_VEC2), 1, value
            )

        def set_vector3(self, name: str, value: tuple[float, float, float]):
            GL.glUniform3fv(
                self._get_typed_uniform_location(name, GL.GL_FLOAT_VEC3), 1, value
            )

        def set_vector4(self, name: str, value: tuple[float, float, float, float]):
            GL.glUniform4fv(
                self._get_typed_uniform_location(name, GL.GL_FLOAT_VEC4), 1, value
            )

        def set_matrix(self, name: str, value: Matrix4x4):
            GL.glUniformMatrix4fv(
                self._get_typed_uniform_location(name, GL.GL_FLOAT_MAT4),
                1,
                True,
                value.values,
            )

        def set_sampler(self, name: str, value: int):
            GL.glUniform1i(
                self._get_typed_uniform_location(name, GL.GL_SAMPLER_2D), value
            )

        @classmethod
        def _compile_shader(cls, type, source: str):
            handle = GL.glCreateShader(type)
            GL.glShaderSource(handle, source)
            GL.glCompileShader(handle)

            compile_status = GL.glGetShaderiv(handle, GL.GL_COMPILE_STATUS)
            if not compile_status:
                compile_log = GL.glGetShaderInfoLog(handle)
                GL.glDeleteShader(handle)

                raise Exception(f"failed to compile shader: {compile_log}")

            return handle

        def _map_uniforms(self):
            self.uniforms = {}
            num_uniforms = GL.glGetProgramiv(self.handle, GL.GL_ACTIVE_UNIFORMS)

            for uniform_index in range(num_uniforms):
                name, size, gl_type = GL.glGetActiveUniform(self.handle, uniform_index)
                name_str = bytes(name).decode("utf-8").rstrip("\0x00")

                location = GL.glGetUniformLocation(self.handle, name_str)
                self.uniforms[name_str] = self.Uniform(
                    name_str, size, gl_type, location
                )

        def _get_typed_uniform_location(self, name: str, gl_type):
            uniform = self.uniforms[name]
            if uniform is not None:
                if uniform.gl_type == gl_type:
                    return uniform.location

            raise Exception(f"uniform {name} does not exist with given type")

    class SceneTexture:
        width: int
        height: int
        levels: int
        pixels: Optional[bytearray]

        def __init__(
            self,
            width: int,
            height: int,
            format,
            levels: int = 1,
            pixels: Optional[bytearray] = None,
        ):
            self.width = width
            self.height = height
            self.format = format
            self.pixels = pixels
            self.levels = levels
            self.handle = None

        def start(self):
            if self.handle is not None:
                raise Exception("texture already started")

            self.handle = GL.glGenTextures(1)

            GL.glBindTexture(GL.GL_TEXTURE_2D, self.handle)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_REPEAT)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)

            if self.pixels is not None:
                GL.glTexImage2D(
                    GL.GL_TEXTURE_2D,
                    0,
                    self.format,
                    self.width,
                    self.height,
                    0,
                    GL.GL_RGBA,
                    GL.GL_UNSIGNED_BYTE,
                    self.pixels,
                )

                if self.levels > 1:
                    GL.glGenerateTextureMipmap(GL.GL_TEXTURE_2D)
            else:
                level_width = self.width
                level_height = self.height
                for level in range(self.levels):
                    pixformat, pixtype = self._get_format_and_type(self.format)
                    GL.glTexImage2D(
                        GL.GL_TEXTURE_2D,
                        level,
                        self.format,
                        level_width,
                        level_height,
                        0,
                        pixformat,
                        pixtype,
                        None,
                    )
                    level_width = max(1, level_width // 2)
                    level_height = max(1, level_height // 2)

            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

        def destroy(self):
            GL.glDeleteTextures(self.handle)
            self.handle = None

        def bind(self, slot: int):
            GL.glActiveTexture(int(GL.GL_TEXTURE0) + slot)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self.handle)

        @classmethod
        def _get_format_and_type(cls, internal_format):
            # fmt: off
            mapping = {
                GL.GL_R8:                 (GL.GL_RED,  GL.GL_UNSIGNED_BYTE),
                GL.GL_R16:                (GL.GL_RED,  GL.GL_UNSIGNED_SHORT),
                GL.GL_R16F:               (GL.GL_RED,  GL.GL_FLOAT),
                GL.GL_R32F:               (GL.GL_RED,  GL.GL_FLOAT),
                GL.GL_RG8:                (GL.GL_RG,   GL.GL_UNSIGNED_BYTE),
                GL.GL_RG16:               (GL.GL_RG,   GL.GL_UNSIGNED_SHORT),
                GL.GL_RG16F:              (GL.GL_RG,   GL.GL_FLOAT),
                GL.GL_RG32F:              (GL.GL_RG,   GL.GL_FLOAT),
                GL.GL_RGB8:               (GL.GL_RGB,  GL.GL_UNSIGNED_BYTE),
                GL.GL_RGB16:              (GL.GL_RGB,  GL.GL_UNSIGNED_SHORT),
                GL.GL_RGB16F:             (GL.GL_RGB,  GL.GL_FLOAT),
                GL.GL_RGB32F:             (GL.GL_RGB,  GL.GL_FLOAT),
                GL.GL_SRGB8:              (GL.GL_RGB,  GL.GL_UNSIGNED_BYTE),
                GL.GL_RGBA8:              (GL.GL_RGBA, GL.GL_UNSIGNED_BYTE),
                GL.GL_RGBA16:             (GL.GL_RGBA, GL.GL_UNSIGNED_SHORT),
                GL.GL_RGBA16F:            (GL.GL_RGBA, GL.GL_FLOAT),
                GL.GL_RGBA32F:            (GL.GL_RGBA, GL.GL_FLOAT),
                GL.GL_SRGB8_ALPHA8:       (GL.GL_RGBA, GL.GL_UNSIGNED_BYTE),
                GL.GL_DEPTH_COMPONENT16:  (GL.GL_DEPTH_COMPONENT, GL.GL_UNSIGNED_SHORT),
                GL.GL_DEPTH_COMPONENT24:  (GL.GL_DEPTH_COMPONENT, GL.GL_UNSIGNED_INT),
                GL.GL_DEPTH_COMPONENT32F: (GL.GL_DEPTH_COMPONENT, GL.GL_FLOAT),
                GL.GL_DEPTH24_STENCIL8:   (GL.GL_DEPTH_STENCIL, GL.GL_UNSIGNED_INT_24_8),
            }
            # fmt: on

            return mapping[internal_format]

    class SceneMesh:
        @dataclass
        class LayoutElement:
            index: int
            size: int
            gl_type: GL.Constant
            stride: int
            offset: int

        FLOAT_SIZE = ctypes.sizeof(ctypes.c_float)
        UINT_SIZE = ctypes.sizeof(ctypes.c_uint32)

        POS_UV_COLOR_NORMAL_LAYOUT = [
            LayoutElement(0, 3, GL.GL_FLOAT, FLOAT_SIZE * 11, FLOAT_SIZE * 0),
            LayoutElement(1, 2, GL.GL_FLOAT, FLOAT_SIZE * 11, FLOAT_SIZE * 3),
            LayoutElement(2, 3, GL.GL_FLOAT, FLOAT_SIZE * 11, FLOAT_SIZE * 5),
            LayoutElement(3, 3, GL.GL_FLOAT, FLOAT_SIZE * 11, FLOAT_SIZE * 8),
        ]

        DEFAULT_SKINNED_STRIDE = FLOAT_SIZE * 15 + UINT_SIZE * 4
        DEFAULT_SKINNED_LAYOUT = [
            LayoutElement(0, 3, GL.GL_FLOAT, DEFAULT_SKINNED_STRIDE, FLOAT_SIZE * 0),
            LayoutElement(1, 2, GL.GL_FLOAT, DEFAULT_SKINNED_STRIDE, FLOAT_SIZE * 3),
            LayoutElement(2, 3, GL.GL_FLOAT, DEFAULT_SKINNED_STRIDE, FLOAT_SIZE * 5),
            LayoutElement(3, 3, GL.GL_FLOAT, DEFAULT_SKINNED_STRIDE, FLOAT_SIZE * 8),
            LayoutElement(4, 4, GL.GL_FLOAT, DEFAULT_SKINNED_STRIDE, FLOAT_SIZE * 11),
            LayoutElement(
                5, 4, GL.GL_UNSIGNED_INT, DEFAULT_SKINNED_STRIDE, FLOAT_SIZE * 15
            ),
        ]

        def __init__(
            self,
            layout: list[LayoutElement],
            vertices: Any,
            indices: Any,
        ):
            self.layout = layout
            self.vertices = vertices
            self.indices = indices
            self.num_indices = len(self.indices)

            self.vertex_buffer = None
            self.index_buffer = None
            self.handle = None

        def start(self):
            if self.handle is not None:
                raise Exception("mesh already started")

            self.handle = GL.glGenVertexArrays(1)
            GL.glBindVertexArray(self.handle)

            self.vertex_buffer = GL.glGenBuffers(1)
            self.index_buffer = GL.glGenBuffers(1)

            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vertex_buffer)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, self.vertices, GL.GL_STATIC_DRAW)

            for layout_element in self.layout:
                match layout_element.gl_type:
                    case GL.GL_INT | GL.GL_UNSIGNED_INT:
                        GL.glVertexAttribIPointer(
                            layout_element.index,
                            layout_element.size,
                            layout_element.gl_type,
                            layout_element.stride,
                            ctypes.c_void_p(layout_element.offset),
                        )
                    case _:
                        GL.glVertexAttribPointer(
                            layout_element.index,
                            layout_element.size,
                            layout_element.gl_type,
                            False,
                            layout_element.stride,
                            ctypes.c_void_p(layout_element.offset),
                        )
                GL.glEnableVertexAttribArray(layout_element.index)

            GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self.index_buffer)
            GL.glBufferData(
                GL.GL_ELEMENT_ARRAY_BUFFER,
                self.indices,
                GL.GL_STATIC_DRAW,
            )

            GL.glBindVertexArray(0)

        def destroy(self):
            GL.glDeleteVertexArrays(self.handle)
            GL.glDeleteBuffers(self.vertex_buffer)
            GL.glDeleteBuffers(self.index_buffer)

            self.handle = None
            self.vertex_buffer = None
            self.index_buffer = None

        def draw(self):
            GL.glBindVertexArray(self.handle)
            GL.glDrawElements(
                GL.GL_TRIANGLES, self.num_indices, GL.GL_UNSIGNED_INT, None
            )

    class PssgViewerCanvas(glcanvas.GLCanvas):
        center: Vector3 = Vector3.zero()
        distance: float = 2.0
        azimuth: float = 0.0
        elevation: float = 0.0

        world_matrix: Matrix4x4 = Matrix4x4.identity()
        view_matrix: Matrix4x4 = Matrix4x4.identity()
        proj_matrix: Matrix4x4 = Matrix4x4.identity()

        pssg_tree: PssgModelTree
        pssg_textures: dict[str, PssgViewerFrame.SceneTexture] = {}
        pssg_meshes: dict[str, PssgViewerFrame.SceneMesh] = {}

        def __init__(self, parent, element: PssgElement):
            gl_attrib_list: list[int] = [
                glcanvas.WX_GL_CORE_PROFILE,
                glcanvas.WX_GL_MAJOR_VERSION,
                4,
                glcanvas.WX_GL_MINOR_VERSION,
                0,
                glcanvas.WX_GL_RGBA,
                glcanvas.WX_GL_DOUBLEBUFFER,
                glcanvas.WX_GL_DEPTH_SIZE,
                24,
                0,
            ]

            super().__init__(parent, attribList=gl_attrib_list)

            self.gl_context = glcanvas.GLContext(self)
            self.gl_initialized = False
            self.prev_mouse_position: Optional[wx.Point] = None

            self.Bind(wx.EVT_SIZE, self.on_resize_viewport)
            self.Bind(wx.EVT_PAINT, self.on_paint)
            self.Bind(wx.EVT_MOTION, self.on_mouse_motion)
            self.Bind(wx.EVT_MOUSEWHEEL, self.on_mouse_scroll)

            self.gl_shader_program = PssgViewerFrame.SceneShader(
                vs_source=VERTEX_SHADER, fs_source=FRAGMENT_SHADER
            )
            self.gl_mesh = PssgViewerFrame.SceneMesh(
                PssgViewerFrame.SceneMesh.POS_UV_COLOR_NORMAL_LAYOUT,
                (ctypes.c_float * len(CUBE_VERTICES))(*CUBE_VERTICES),
                (ctypes.c_uint32 * len(CUBE_INDICES))(*CUBE_INDICES),
            )

            self.pssg_tree = PssgModelTree(element)

        def on_mouse_scroll(self, event: wx.MouseEvent):
            delta = event.GetWheelRotation() / event.GetWheelDelta()
            self.distance = self.distance - delta * 0.05

        def on_mouse_motion(self, event: wx.MouseEvent):
            current_mouse_pos = event.GetPosition()
            if event.Dragging() and event.LeftIsDown():
                if self.prev_mouse_position is None:
                    self.prev_mouse_position = current_mouse_pos
                    return

                delta_x = current_mouse_pos.x - self.prev_mouse_position.x
                delta_y = current_mouse_pos.y - self.prev_mouse_position.y
                self.prev_mouse_position = current_mouse_pos

                delta_yaw = delta_x / 300.0
                delta_pitch = delta_y / 300.0

                self.elevation = self.elevation - delta_pitch
                self.azimuth = self.azimuth - delta_yaw
            else:
                self.prev_mouse_position = None

        def on_resize_viewport(self, event: wx.SizeEvent):
            event.Skip()
            self.Refresh()

        def on_paint(self, event: wx.PaintEvent):
            wx.PaintDC(self)

            if not self.IsShownOnScreen():
                return

            self.SetCurrent(self.gl_context)
            self._initialize_if_needed()
            self.on_render()

        def on_render(self):
            if not self.gl_initialized:
                return

            vp_size = self.GetClientSize()

            self.view_matrix = Matrix4x4.translation(-self.center)
            self.view_matrix = Matrix4x4.rotation_y(-self.azimuth) * self.view_matrix
            self.view_matrix = Matrix4x4.rotation_x(-self.elevation) * self.view_matrix
            self.view_matrix = (
                Matrix4x4.translation(Vector3(0, 0, -self.distance)) * self.view_matrix
            )
            self.proj_matrix = Matrix4x4.perspective(
                vp_size.width / vp_size.height, math.pi * 0.5, 0.05, 100.0
            )

            GL.glEnable(GL.GL_DEPTH_TEST)
            GL.glViewport(0, 0, vp_size.width, vp_size.height)
            GL.glClearColor(0.207, 0.36, 0.64, 1)
            GL.glClear(int(GL.GL_COLOR_BUFFER_BIT) | int(GL.GL_DEPTH_BUFFER_BIT))

            self.gl_shader_program.bind()
            self.gl_shader_program.set_matrix("u_world", self.world_matrix)
            self.gl_shader_program.set_matrix("u_view", self.view_matrix)
            self.gl_shader_program.set_matrix("u_projection", self.proj_matrix)

            # reference cube to be removed later
            self.gl_shader_program.set_vector4("u_color", (1.0, 1.0, 1.0, 1.0))
            self.gl_shader_program.set_flag("u_use_diffuse", False)
            self.gl_shader_program.set_sampler("u_diffuse", 0)
            self.gl_mesh.draw()

            # render pssg scene
            self.pssg_tree.compute_transforms()
            for _, node in self.pssg_tree.rendernodes.items():
                world = self.world_matrix * node.model_matrix
                pssg_gl_mesh = self.pssg_meshes[node.id]

                if node.texture is not None:
                    pssg_gl_texture = self.pssg_textures[node.texture.id]
                    pssg_gl_texture.bind(0)

                    self.gl_shader_program.set_flag("u_use_diffuse", True)
                    self.gl_shader_program.set_sampler("u_diffuse", 0)
                else:
                    GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
                    self.gl_shader_program.set_flag("u_use_diffuse", False)

                self.gl_shader_program.set_matrix("u_world", world)
                pssg_gl_mesh.draw()

            self.SwapBuffers()

        def _initialize_if_needed(self):
            if not self.gl_initialized:
                self.gl_version = GL.glGetString(GL.GL_VERSION)
                self.gl_initialized = True

                logging.info("opengl version: %s", self.gl_version.decode("utf-8"))  # type: ignore

                self.gl_shader_program.start()
                self.gl_mesh.start()
                self._init_pssg_model_resources()

                logging.info(self.gl_shader_program.uniforms)

        def _init_pssg_model_resources(self):
            for id, rendernode in self.pssg_tree.rendernodes.items():
                self.pssg_meshes[id] = PssgViewerFrame.SceneMesh(
                    PssgViewerFrame.SceneMesh.DEFAULT_SKINNED_LAYOUT,
                    (ctypes.c_ubyte * len(rendernode.vertex_buffer)).from_buffer(
                        rendernode.vertex_buffer
                    ),
                    (ctypes.c_ubyte * len(rendernode.index_buffer)).from_buffer(
                        rendernode.index_buffer
                    ),
                )
                self.pssg_meshes[id].start()

            for id, texturenode in self.pssg_tree.textures.items():
                self.pssg_textures[id] = PssgViewerFrame.SceneTexture(
                    texturenode.width,
                    texturenode.height,
                    GL.GL_RGBA8,
                    1,
                    texturenode.texels,
                )
                self.pssg_textures[id].start()

            # make the model fit the viewport easily
            min_bounds, max_bounds = self._calculate_model_bounds()
            model_center = (min_bounds + max_bounds) * 0.5
            model_span = (max_bounds - min_bounds) * 0.5

            model_span.x = model_span.x if model_span.x > 0.0 else 1.0
            model_span.y = model_span.y if model_span.y > 0.0 else 1.0
            model_span.z = model_span.z if model_span.z > 0.0 else 1.0

            scale = 1.0 / max(model_span.x, model_span.y, model_span.z)
            self.world_matrix = Matrix4x4.scale(
                Vector3(scale, scale, scale)
            )  # * Matrix4x4.translation(-model_center)

        def _calculate_model_bounds(self) -> tuple[Vector3, Vector3]:
            min_bounds = Vector3.zero()
            max_bounds = Vector3.zero()
            has_any_bounds = False

            self.pssg_tree.compute_transforms()
            for node in self.pssg_tree.iter_nodes():
                node_min_bounds = node.model_matrix * node.bounding_min
                node_max_bounds = node.model_matrix * node.bounding_max

                min_bounds.x = min(node_min_bounds.x, node_max_bounds.x, min_bounds.x)
                min_bounds.y = min(node_min_bounds.y, node_max_bounds.y, min_bounds.y)
                min_bounds.z = min(node_min_bounds.z, node_max_bounds.z, min_bounds.z)

                max_bounds.x = max(node_min_bounds.x, node_max_bounds.x, max_bounds.x)
                max_bounds.y = max(node_min_bounds.y, node_max_bounds.y, max_bounds.y)
                max_bounds.z = max(node_min_bounds.z, node_max_bounds.z, max_bounds.z)

                has_any_bounds = True

            if has_any_bounds:
                return (min_bounds, max_bounds)
            else:
                return (Vector3(-1, -1, -1), Vector3(1, 1, 1))

    def __init__(self, title: str, element: PssgElement):
        wx.Frame.__init__(
            self,
            None,
            title=title,
            pos=wx.DefaultPosition,
            size=wx.Size(640, 480),
            style=wx.DEFAULT_FRAME_STYLE | wx.NO_FULL_REPAINT_ON_RESIZE,
        )

        self.element = element
        self.canvas = self.PssgViewerCanvas(self, self.element)

        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()
        file_menu_exit = file_menu.Append(
            wx.ID_EXIT, "E&xit\tAlt+X", "close the viewer window"
        )
        menu_bar.Append(file_menu, "&File")

        self.status_bar = self.CreateStatusBar()

        self.SetMenuBar(menu_bar)
        self.SetStatusBar(self.status_bar)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.canvas, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.timer = wx.Timer(self)
        self.timer.Start(10)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_MENU, self.on_close, file_menu_exit)
        self.Bind(wx.EVT_TIMER, self.on_timer)

    def on_close(self, event: wx.Event):
        self.Destroy()

    def on_timer(self, event: wx.TimerEvent):
        self.canvas.on_render()


class PssgJsonEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        if isinstance(o, Enum):
            return o.name
        if isinstance(o, bytes):
            return o.hex()

        return super().default(o)


def _write_pssg_as_json(pssg_element: PssgElement, output_path: pathlib.Path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pssg_element, f, cls=PssgJsonEncoder, indent=4)


def main() -> int:
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s][%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    arg_parser = argparse.ArgumentParser(
        prog="pssgparser", description="simple python pssg parser for atelier meruru"
    )
    arg_parser.add_argument("-i", "--input", required=True, help="input pssg filename")
    args = arg_parser.parse_args()

    input_filename = args.input
    try:
        pssg_reader = PssgReader(input_filename)

        logging.info("loaded pssg file")
        # for pssg_schema_element in pssg_reader.pssg_schema_elements:
        #     logging.info("found pssg schema element %s", pssg_schema_element)
        #
        # for pssg_schema_attrib in pssg_reader.pssg_schema_attribs:
        #     logging.info("found pssg schema attribute %s", pssg_schema_attrib)

        viewer_app = wx.App()
        viewer_app_frame = PssgViewerFrame(input_filename, pssg_reader.pssg_tree)
        viewer_app_frame.Show()
        viewer_app.MainLoop()

    except Exception as e:
        logging.error("failed to parse pssg file: %s", str(e))

    return 0


if __name__ == "__main__":
    sys.exit(main())
