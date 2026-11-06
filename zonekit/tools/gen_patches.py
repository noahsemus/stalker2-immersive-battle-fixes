"""Write ImmersiveBattleFixes' cfg patches into the kit plugin (then mirror_from_kit.ps1 copies them into the repo).

Usage (kit's embedded Python):  python.exe -I zonekit/tools/gen_patches.py [--dry]
Every patch is a {bpatch} of one vanilla spawn actor or one vanilla quest node; the vanilla files are read first
and every GUID / node / member named here is checked against them, so a typo stops the run instead of shipping.
Battle data lives in BATTLES below; PLAN.md says what each battle needs and why.
"""
import json, os, re, sys

MOD = "ImmersiveBattleFixes"
SETTINGS = os.path.join(os.environ["LOCALAPPDATA"], "stalker2-modding-harness", "settings.json")
KIT = json.load(open(SETTINGS, encoding="utf-8-sig"))["kit"]
GD = os.path.join(KIT, "Stalker2", "Content", "GameLite", "GameData")
OUT = os.path.join(KIT, "Stalker2", "Mods", MOD, "Content", "GameLite", "GameData")
SAP = "SpawnActorPrototypes/WorldMap_WP"
TAG = "ImmersiveBattleFixes b1"

# ---------------------------------------------------------------------------------------------------------------
# Battle data. Squads: squad GUID -> members to KEEP (vanilla order) or ("generic", count). Members referenced by
# quest nodes on their own GUID are kept (the generator checks this). Damage: DamageMultiplier on every kept member.
# Nodes: quest node SID -> {field: value} set by bpatch.
# ---------------------------------------------------------------------------------------------------------------
BATTLES = {
    "E16_MQ01_C03": {  # Granite fight at the Generators (every ending). Tester 2026-11-06: heavy cut, 65% damage,
                       # no ambush (elites visible, snipers do not know where you are when they come out).
        "level": "E16_MQ01_C03_LogicLevel_WP",
        "damage": 0.65,
        "squads": {
            "9532FC3A448DD3AB81562D95C91BE9BA": ["9D8254B6458271C223A98DB7AD0B3667"],  # Respawnable: CC (1 of 1)
            "74D8C40A445CCF28988BF7B2ECEF2C7E": ["F09A16114121EFF44C00409243D7D4FE"],  # Respawnable_1: Storm (of 2 Sn + 2 St)
            "C754B6B54A130E3920F8B89A64C6BA7C": ["011CC4E948076BF17D2C2FB0A0A8EB30"],  # SqThree: Storm (has a space restriction) of CC + St
            "EB55A9AC49F72D5E01EB768CB752216F": ["D51DF6C84444635D87DDEDB9AB42548F"],  # SqFour: Storm of Sn + St
            "50A6E9564032C8553B2F8AAB57793064": ["03429CE74D9E342C6D8890A71FEFDD52"],  # SqFive: CC of CC + St
            "C6C7E2D74919ACAEFD460BB01111381C": ["00AF2A234D960C9D1A9BCFA09ED427F7"],  # SqSix: Storm of St, CC, St
            "418687B24CBACA896AC74A8CE7C8A249": ["20F2CE55427FF2AEB99A0F8E496110E7"],  # SqSeven: Storm of St + Sn
            "9CA2F72B413CBCD5B80B59ADBCC9A20E": ["4116388D4891565BF43F7CA4D764EDC7"],  # SqNine: 1 of 3 Storm
            "783F761741CEDAD3C854558219366256": ["8367732844E5C853B305D0952E6149CB",   # SqTen: Storm + Sniper of 4 St + 2 Sn
                                                 "9255ACA14859C42E157E888C13674203"],
            "86C5DCEF4527E3157A4E1E9DDF31ECA7": ["E03AB8E34FC8390B25BA1A91A3EE2137",   # SqEleven: both (each has its own
                                                 "2940374D41281BB8DD32B483FD07FC15"],  #   MoveTo / Kill nodes)
            "B199C7E24943A4A67FB5E3B759E17010": ["39AA5A8346F679B346338A880BE1D161",   # Elites: CC + Storm of 2 CC + 2 St
                                                 "42A1F4864E1D4BBF49A95A965786E4A4"],
            "5756FC6D4440384537DD448E78CE8A5F": ("generic", 1),                        # SqOne2: 1 of 3 generic Granit
            "29525D88462F25A0A87B87A3631A928B": ["6006E8DF4D58BE8EF364BCAE70ED4617"],  # Snipers (Gauss): 1 of 5
            "DF1671714F801E893A787DAE82A468E0": ["BA9A8629420055D60C050CA09BBEDFC0"],  # FinalSquad: CC (1 of 1)
        },
        "singles": ["B6A0EEDD400293A089279C8FE831EAB0"],  # CptPrice: one Granit_CloseCombat (Obj spawn)
        "nodes": {
            # elites no longer spawn invisible: the hide node shows them instead (its Unhide twin stays as is)
            "E16_MQ01_C03_ToggleNPCHidden_BP_SquadPlaceholder_E16_MQ01_C03_Granit_Elites":
                {"HideViewType": "EHideViewType::Unhide"},
            # snipers come out of their doors without knowing at once where the player is
            # (IgnoreThreat off too: vanilla pairs ImmediatelyIdentifyEnemy = false with IgnoreThreat = true only on
            # one boss; a sniper that ignores threats and never identifies the player could stay put and stall the
            # stage, which needs the snipers' squad dead)
            "E16_MQ01_C03_SetAIBehavior_SnipersKillPlayer": {"ImmediatelyIdentifyEnemy": "false",
                                                             "IgnoreThreat": "false"},
        },
        # b1 PROBE (remove for release): the first Granite (Respawnable CC) at 10% instead of 65%, so the tester can
        # tell which way DamageMultiplier works: his shotgun barely hurts = outgoing (as assumed); he takes ages to
        # kill = it scales damage TAKEN (then this field cannot lower their damage and we need another lever).
        "damage_override": {"9D8254B6458271C223A98DB7AD0B3667": 0.1},
    },
}


def read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def write(rel, text, dry):
    path = os.path.join(OUT, rel.replace("/", os.sep))
    if dry:
        print(f"--- {rel}\n{text}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)


def actor_patch(guid, body_lines):
    return "\n".join([f"// {TAG}", f"{guid} : struct.begin {{bpatch}}"] + ["   " + l for l in body_lines] + ["struct.end", ""])


def main():
    dry = "--dry" in sys.argv
    written = []
    for quest, b in BATTLES.items():
        lvl_dir = os.path.join(GD, SAP, b["level"])
        qtext = read(os.path.join(GD, "QuestNodePrototypes", quest + ".cfg"))
        # every quest file, to find quest nodes that name a squad member we drop
        allq = {fn: read(os.path.join(GD, "QuestNodePrototypes", fn))
                for fn in os.listdir(os.path.join(GD, "QuestNodePrototypes")) if fn.endswith(".cfg")}
        total_before = total_after = 0
        for squad, keep in b["squads"].items():
            vtext = read(os.path.join(lvl_dir, squad + ".cfg"))
            if "SpawnType = ESpawnType::Squad" not in vtext:
                sys.exit(f"{squad}: not a squad")
            if isinstance(keep, tuple):
                n = int(re.search(r"SpawnedSquadMembersCount = (\d+)", vtext).group(1))
                total_before += n
                total_after += keep[1]
                # the list re-emitted whole (plain struct inside the bpatch): a single-index bpatch of a list has
                # replaced the whole list in game before. No DamageMultiplier: squads don't pass one to generic
                # members (vanilla squads never set it and the base default is 0).
                proto = re.search(r"SpawnedGenericMembers : struct\.begin.*?SpawnedPrototypeSID = (\S+)", vtext, re.S).group(1)
                body = ["SpawnedGenericMembers : struct.begin",
                        "   [0] : struct.begin",
                        f"      SpawnedSquadMembersCount = {keep[1]}",
                        f"      SpawnedPrototypeSID = {proto}",
                        "   struct.end",
                        "struct.end"]
                write(f"{SAP}/{b['level']}/{squad}/{squad}_patch_{MOD}.cfg", actor_patch(squad, body), dry)
                written.append(squad)
                continue
            block = re.search(r"SquadMembersQuestSIDs : struct\.begin(.*?)struct\.end", vtext, re.S).group(1)
            members = re.findall(r"\[\d+\] = ([0-9A-F]{32})", block)
            total_before += len(members)
            total_after += len(keep)
            for k in keep:
                if k not in members:
                    sys.exit(f"{squad}: kept member {k} is not in the vanilla list")
            for m in members:
                if m in keep:
                    continue
                users = [fn for fn, t in allq.items() if m in t]
                if users:
                    sys.exit(f"{squad}: dropped member {m} is named by quest nodes in {users}; keep it")
            body = ["SquadMembersQuestSIDs : struct.begin"]  # plain struct inside the bpatch: replaces the list whole
            body += [f"   [{i}] = {g}" for i, g in enumerate(keep)]
            body += ["struct.end"]
            write(f"{SAP}/{b['level']}/{squad}/{squad}_patch_{MOD}.cfg", actor_patch(squad, body), dry)
            written.append(squad)
            for g in keep:
                mt = read(os.path.join(lvl_dir, g + ".cfg"))
                if "SpawnType = ESpawnType::Obj" not in mt or "DamageMultiplier = 1" not in mt:
                    sys.exit(f"{g}: expected an Obj spawn with DamageMultiplier = 1")
                dm = b.get("damage_override", {}).get(g, b["damage"])
                write(f"{SAP}/{b['level']}/{g}/{g}_patch_{MOD}.cfg", actor_patch(g, [f"DamageMultiplier = {dm}"]), dry)
                written.append(g)
        for g in b.get("singles", []):
            mt = read(os.path.join(lvl_dir, g + ".cfg"))
            if "SpawnType = ESpawnType::Obj" not in mt or "DamageMultiplier = 1" not in mt:
                sys.exit(f"{g}: expected an Obj spawn with DamageMultiplier = 1")
            total_before += 1
            total_after += 1
            write(f"{SAP}/{b['level']}/{g}/{g}_patch_{MOD}.cfg", actor_patch(g, [f"DamageMultiplier = {b['damage']}"]), dry)
            written.append(g)
        # quest nodes
        lines = [f"// {TAG}"]
        for sid, fields in b["nodes"].items():
            m = re.search(rf"^{re.escape(sid)} : struct\.begin(.*?)^struct\.end", qtext, re.M | re.S)
            if not m:
                sys.exit(f"{quest}: node {sid} not found")
            lines.append(f"{sid} : struct.begin {{bpatch}}")
            for k, v in fields.items():
                if not re.search(rf"^\s*{k} = ", m.group(1), re.M):
                    sys.exit(f"{sid}: vanilla node has no field {k}")
                lines.append(f"   {k} = {v}")
            lines.append("struct.end")
        write(f"QuestNodePrototypes/{quest}/{quest}_patch_{MOD}.cfg", "\n".join(lines) + "\n", dry)
        print(f"{quest}: {total_before} -> {total_after} enemies, {len(written)} actor patches, {len(b['nodes'])} node patches")


if __name__ == "__main__":
    main()
