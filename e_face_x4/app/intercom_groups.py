"""Validation and composition of e-Face Intercom groups."""
import re

GROUP = re.compile(r"(?:828[0-9]|8290)\Z")
MEMBER = re.compile(r"(?:829[1-9]|83[0-9]{2})\Z")

def validate(groups):
    if not isinstance(groups, list) or len(groups) > 11: raise ValueError("Massimo undici gruppi")
    result=[]; used=set()
    for item in groups:
        if not isinstance(item,dict) or set(item)!={"extension","name","members"}: raise ValueError("Dati gruppo incompleti")
        ext,name,members=item["extension"],item["name"],item["members"]
        if not isinstance(ext,str) or not GROUP.fullmatch(ext) or ext in used: raise ValueError("Numero gruppo non valido")
        if not isinstance(name,str) or not 1 <= len(name.strip()) <= 48: raise ValueError("Nome gruppo non valido")
        if not isinstance(members,list) or any(not isinstance(x,str) or not MEMBER.fullmatch(x) for x in members): raise ValueError("Interni non validi")
        used.add(ext); result.append({"extension":ext,"name":name.strip(),"members":sorted(set(members))})
    return sorted(result,key=lambda x:x["extension"])

def available_members(records=None):
    from . import control4_tablets, personal_devices, voip_phones
    fixed=[{"extension":"8291","name":"Ufficio","kind":"control4","video_capable":False},{"extension":"8292","name":"Tavolo","kind":"control4","video_capable":False}]
    fixed += [{"extension":x["extension"],"name":x["name"],"kind":"control4","video_capable":False} for x in control4_tablets.load()]
    fixed += [{"extension":x["extension"],"name":x["name"],"kind":"personal","dnd":x["dnd"],"video_capable":x["video_capable"],"video_enabled":x["video_enabled"]} for x in personal_devices.public(personal_devices.load() if records is None else records)]
    fixed += [{"extension":extension,"name":record["name"],"kind":"voip","video_capable":record["profile"]=="voip_video"} for extension,record in voip_phones.load().items()]
    return fixed

def with_default(groups, records=None):
    custom=[x for x in validate(groups) if x["extension"] != "8290"]
    members=[x["extension"] for x in available_members(records) if x.get("kind") == "control4" or not x.get("dnd")]
    return validate([{"extension":"8290","name":"Tutti","members":members},*custom])
