"""Click-triggered 'Appear' animations.

python-pptx has no animation API, so this writes the PowerPoint timing XML
directly into the slide. Shapes given to appear_on_click() are hidden when
the slideshow reaches the slide and appear group by group, one click each,
in the given order. Editing view shows everything (stacked).
"""
from __future__ import annotations

from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn

_EFFECT = (
    '<p:par><p:cTn id="{id0}" presetID="1" presetClass="entr" presetSubtype="0"'
    ' fill="hold" grpId="0" nodeType="{node}">'
    '<p:stCondLst><p:cond delay="0"/></p:stCondLst>'
    '<p:childTnLst><p:set><p:cBhvr>'
    '<p:cTn id="{id1}" dur="1" fill="hold">'
    '<p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
    '<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'
    '<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>'
    '</p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>'
    '</p:childTnLst></p:cTn></p:par>'
)

_CLICK = (
    '<p:par><p:cTn id="{id0}" fill="hold">'
    '<p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>'
    '<p:childTnLst><p:par><p:cTn id="{id1}" fill="hold">'
    '<p:stCondLst><p:cond delay="0"/></p:stCondLst>'
    '<p:childTnLst>{effects}</p:childTnLst>'
    '</p:cTn></p:par></p:childTnLst></p:cTn></p:par>'
)

_TIMING = (
    '<p:timing {ns}><p:tnLst><p:par>'
    '<p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">'
    '<p:childTnLst><p:seq concurrent="1" nextAc="seek">'
    '<p:cTn id="2" dur="indefinite" nodeType="mainSeq">'
    '<p:childTnLst>{clicks}</p:childTnLst></p:cTn>'
    '<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
    '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>'
    '</p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>'
)


def appear_on_click(slide, groups):
    """Reveal shapes with the 'Appear' entrance effect, one click per group.

    groups: sequence of shapes, or sequence of shape-lists (shapes revealed
    together on the same click). Replaces any existing slide timing.
    """
    groups = [g if isinstance(g, (list, tuple)) else [g] for g in groups]
    groups = [g for g in groups if g]
    if not groups:
        return

    next_id = 3
    clicks = []
    for group in groups:
        effects = []
        for j, shape in enumerate(group):
            effects.append(_EFFECT.format(
                id0=next_id, id1=next_id + 1, spid=shape.shape_id,
                node="clickEffect" if j == 0 else "withEffect"))
            next_id += 2
        clicks.append(_CLICK.format(id0=next_id, id1=next_id + 1,
                                    effects="".join(effects)))
        next_id += 2

    sld = slide._element
    for el in sld.findall(qn("p:timing")):
        sld.remove(el)
    sld.append(parse_xml(_TIMING.format(ns=nsdecls("p"), clicks="".join(clicks))))
