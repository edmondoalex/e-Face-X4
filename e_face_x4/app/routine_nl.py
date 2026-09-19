"""Conservative Italian text-to-routine draft builder.

Only explicit, unambiguous instructions are accepted. The resulting spec still
goes through the normal live-catalog validation and is never activated here.
"""
from __future__ import annotations

import re
import unicodedata


def _fold(value: str) -> str:
    return " ".join("".join(char for char in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(char)).split())


def _device(phrase: str, devices: list[dict], *, allowed: set[str] | None = None) -> dict:
    text = _fold(phrase)
    matches = []
    for device in devices:
        if allowed and device.get("kind") not in allowed:
            continue
        name = _fold(str(device.get("name") or ""))
        if name and len(name) >= 3 and re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text):
            matches.append(device)
    if not matches:
        raise ValueError(f"Non trovo un dispositivo nominato in «{phrase.strip()}». Usa il nome completo mostrato in e-Face.")
    longest = max(len(_fold(str(device.get("name") or ""))) for device in matches)
    matches = [device for device in matches if len(_fold(str(device.get("name") or ""))) == longest]
    if len(matches) > 1:
        qualifier = text
        for device in matches:
            qualifier = qualifier.replace(_fold(str(device.get("name") or "")), " ")
        room_matches = [device for device in matches if _fold(str(device.get("room") or "")) and _fold(str(device.get("room") or "")) in qualifier]
        if len(room_matches) == 1:
            return room_matches[0]
        raise ValueError(f"Nome ambiguo in «{phrase.strip()}»: {', '.join(str(item.get('name')) + ' (' + str(item.get('room') or 'senza stanza') + ')' for item in matches[:5])}.")
    return matches[0]


def _trigger(phrase: str, devices: list[dict]) -> dict:
    text = _fold(phrase)
    clock = re.fullmatch(r"(?:alle|ogni giorno alle)\s+([01]?\d|2[0-3]):([0-5]\d)", text)
    if clock:
        return {"type": "time", "at": f"{int(clock[1]):02d}:{clock[2]}"}
    solar = re.fullmatch(r"(?:all[ao]|al|alla)\s+(alba|tramonto)(?:\s+(\d{1,3})\s+minut[oi]\s+(prima|dopo))?", text)
    if solar:
        return {"type": "sun", "event": "sunrise" if solar[1] == "alba" else "sunset", "offset_minutes": (-1 if solar[3] == "prima" else 1) * int(solar[2] or 0)}
    if text in {"doorbird suona", "suona doorbird", "doorbird pulsante"}:
        return {"type": "doorbird", "event": "doorbell"}
    state = next(((pattern, value) for pattern, value in [
        (r"\b(?:si accende|diventa on|va in on)\b", "on"),
        (r"\b(?:si spegne|diventa off|va in off)\b", "off"),
        (r"\b(?:rileva movimento|diventa active|va in active)\b", "active"),
        (r"\b(?:si apre|diventa open)\b", "open"),
        (r"\b(?:si chiude|diventa closed)\b", "closed"),
    ] if re.search(pattern, text)), None)
    if not state:
        raise ValueError("Attivazione non riconosciuta: scrivi per esempio «Quando Luce Ufficio si accende» oppure «Alle 18:30».")
    device = _device(phrase, devices)
    remainder = text.replace(_fold(str(device.get("name") or "")), " ", 1)
    if device.get("room"):
        remainder = remainder.replace(_fold(str(device["room"])), " ", 1)
    remainder = re.sub(state[0], " ", remainder, count=1)
    if remainder.strip(" ,.;:'\" "):
        raise ValueError(f"Non capisco tutta l'attivazione «{phrase.strip()}»: specifica un solo evento.")
    target = "command_" + state[1] if device.get("kind") == "light_scenario" and state[1] in {"on", "off"} else state[1]
    return {"type": "state", "device_id": str(device["id"]), "to": target}


def _action(phrase: str, devices: list[dict]) -> dict:
    text = _fold(phrase)
    commands = [
        (r"^(?:accendi|attiva)\b", "on", {"light", "light_scenario", "switch"}),
        (r"^(?:spegni|disattiva)\b", "off", {"light", "light_scenario", "switch"}),
        (r"^apri\b", "open", {"cover"}),
        (r"^chiudi\b", "close", {"cover"}),
        (r"^riproduci\b", "media_play", {"media_player"}),
        (r"^metti in pausa\b", "media_pause", {"media_player"}),
        (r"^ferma\b", "media_stop", {"media_player"}),
    ]
    for pattern, command, kinds in commands:
        matched = re.search(pattern, text)
        if matched:
            device = _device(phrase, devices, allowed=kinds)
            remainder = text[matched.end():].replace(_fold(str(device.get("name") or "")), " ", 1)
            if device.get("room"):
                remainder = remainder.replace(_fold(str(device["room"])), " ", 1)
            remainder = re.sub(r"\b(?:la|il|lo|l|i|gli|le|di|del|della|nella|nel|in|a|al|alla)\b", " ", remainder)
            if remainder.strip(" ,.;:'\" "):
                raise ValueError(f"Non capisco tutta l'azione «{phrase.strip()}»: specifica una sola azione e il nome completo del dispositivo.")
            return {"type": "action", "device_id": str(device["id"]), "action": command}
    raise ValueError(f"Azione non riconosciuta in «{phrase.strip()}». Usa un comando come accendi, spegni, apri o chiudi e il nome completo del dispositivo.")


def from_text(text: str, devices: list[dict], name: str = "") -> dict:
    if not isinstance(text, str) or not 12 <= len(text.strip()) <= 2000:
        raise ValueError("Descrivi la routine in 12–2000 caratteri.")
    description = " ".join(text.strip().replace("\n", " ").split()).rstrip(".!")
    match = re.fullmatch(r"(?i)quando\s+(.+?)(?:,|\s+allora\s+)\s*(.+)", description)
    if match:
        trigger_text, action_text = match.group(1), match.group(2)
    else:
        match = re.fullmatch(r"(?i)(alle\s+\d{1,2}:\d{2}|(?:all[ao]|al|alla)\s+(?:alba|tramonto)(?:\s+\d+\s+minut[oi]\s+(?:prima|dopo))?)\s*,?\s+(.+)", description)
        if not match:
            raise ValueError("Separa attivazione e azioni con una virgola o «allora»: «Quando Luce Ufficio si accende, accendi Luce Corridoio».")
        trigger_text, action_text = match.group(1), match.group(2)
    trigger = _trigger(trigger_text, devices)
    steps = []
    for part in re.split(r"\s+(?:e poi|poi|e)\s+", action_text, flags=re.I):
        part = part.strip(" ,")
        delayed = re.fullmatch(r"(?i)dopo\s+(\d{1,4})\s+(second[oi]|minut[oi])\s+(.+)", part)
        if delayed:
            seconds = int(delayed[1]) * (60 if delayed[2].casefold().startswith("minut") else 1)
            steps.append({"type": "wait", "seconds": seconds})
            part = delayed[3]
        duration = re.fullmatch(r"(?i)(.+?)\s+per\s+(\d{1,4})\s+(second[oi]|minut[oi])", part)
        if duration:
            part = duration[1]
        wait = re.fullmatch(r"(?i)(?:aspetta|attendi|dopo)\s+(\d{1,4})\s+(second[oi]|minut[oi])", part)
        if wait:
            seconds = int(wait[1]) * (60 if wait[2].casefold().startswith("minut") else 1)
            steps.append({"type": "wait", "seconds": seconds})
        else:
            steps.append(_action(part, devices))
        if duration:
            steps.append({"type": "wait", "seconds": int(duration[2]) * (60 if duration[3].casefold().startswith("minut") else 1)})
    if not steps or steps[-1]["type"] == "wait":
        raise ValueError("Aggiungi un'azione dopo il timer.")
    return {"name": name.strip()[:80] or description[:80], "triggers": [trigger], "conditions": [], "steps": steps}
