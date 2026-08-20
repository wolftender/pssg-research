import os
import sys
import struct
import argparse
import pathlib
import logging
import json
import dataclasses

from array import array
from enum import Enum
from typing import Any
from dataclasses import dataclass

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

    def _pssg_read_n_u8(self, n: int) -> tuple[int, ...]:
        values = struct.unpack_from(f">{n}B", self.pssg_buffer, self.buffer_offset)
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
                logging.warning(f"failed to parse element {pssg_schema_element.name}, save as raw buffer")
                has_valid_subtree = False

        if not has_valid_subtree:
            self.buffer_offset = pssg_element_data_start_offset
            element_data_size = pssg_element_end_offs - self.buffer_offset
            pssg_element.value = self._pssg_parse_element_value(pssg_schema_element.type, element_data_size)


        self.buffer_offset = pssg_element_end_offs
        return pssg_element


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
        for pssg_schema_element in pssg_reader.pssg_schema_elements:
            logging.info("found pssg schema element %s", pssg_schema_element)

        for pssg_schema_attrib in pssg_reader.pssg_schema_attribs:
            logging.info("found pssg schema attribute %s", pssg_schema_attrib)

        _write_pssg_as_json(pssg_reader.pssg_tree, pathlib.Path("out.json"))

    except Exception as e:
        logging.error("failed to parse pssg file: %s", str(e))

    return 0


if __name__ == "__main__":
    sys.exit(main())
