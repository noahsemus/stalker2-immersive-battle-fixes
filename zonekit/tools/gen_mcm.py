"""Generates the paste text of ImmersiveBattleFixes' two Blueprints (MCM support, build 2).

BP_ImmBFSubsystem (ModWorldSubsystem), whole event graph:
  OnInitialized -> SetTickEnabled(true)
  OnTick -> Provider invalid and fewer than 5 failed loads? -> LoadClassAsset_Blocking(BP_ImmBFMCM, by soft class
            path) -> loaded (MCM installed)? spawn it, else count the failure. The main mod never imports MCM, so it
            loads and plays with its defaults without MCM.
BP_ImmBFMCM (Actor implementing /ModConfigurationMenu/BPI_MCM_SettingsProvider), whole event graph. MCM's manager
finds it (GetAllActorsWithInterface) ~5 s after each load and calls:
  RegisterMCMSettings(api)        -> RegisterModSetting per setting (current value; a value MCM saved wins),
                                     AddUniqueModID, Registered = true
  RegisterMCMDefaultSettings(api) -> RegisterDefaultModSetting per setting
  ApplyMCMSettings(api)           -> (once registered) GetModSetting per setting -> variable, then for each setting
                                     start the setter quest node of its value (gen_patches.py writes them into a
                                     rootgraph patch: ImmBF_Set_<Key>_<value>) with CppMediator.StartQuestNode, and
                                     the same node by console (XStartQuestNodeBySID) as a twin: neither is proven
                                     from Blueprint, running both twice only sets the same value twice.
The MCM nodes (interface events, the (Message) calls) are lifted from MCM's own example (MCM_ModExample1, exported
with harness/tools/editor/export_t3d.py); their pin formats must match the interface exactly
(ImmersiveLooting gen_mcm_provider.py, harness/docs/compatibility.md § MCM).
Usage: python gen_mcm.py <BP_MCM_ModExample1.t3d> <out_dir>   -> <out_dir>/<Blueprint>/EventGraph.txt + pages.json
(one paste window per Blueprint: harness/tools/paste_pages.ps1 -Dir <out_dir>/<Blueprint>)
"""
import os
import re
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "harness", "tools", "t3d"))
from bp_t3d import cls, TGT, write
from bp_graph import Graph, Node, page_digest
from t3d_lift import Lifted, link

EX, OUT = sys.argv[1], sys.argv[2]
BG = "/Script/BlueprintGraph."
RT = "/ImmersiveBattleFixes/Runtime"
MCM_CLS = f"\"/Script/Engine.BlueprintGeneratedClass'{RT}/BP_ImmBFMCM.BP_ImmBFMCM_C'\""
SUB_CLS = f"\"/Script/Engine.BlueprintGeneratedClass'{RT}/BP_ImmBFSubsystem.BP_ImmBFSubsystem_C'\""
OBJ = cls("/Script/CoreUObject.Object")
ACTOR = cls("/Script/Engine.Actor")
MWS = cls("/Script/Stalker2.ModWorldSubsystem")
KSL = cls("/Script/Engine.KismetSystemLibrary")
KML = cls("/Script/Engine.KismetMathLibrary")
CPP = cls("/Script/Stalker2.CppMediator")
PC_CLS = cls("/Script/Engine.PlayerController")
SID_T = "\"/Script/CoreUObject.ScriptStruct'/Script/Stalker2.PrototypeSID'\""
XFORM = "\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.Transform'\""
VEC = "\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.Vector'\""
ROT = "\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.Rotator'\""
SCPS = "\"/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.SoftClassPath'\""
EN = lambda p: f"\"/Script/CoreUObject.Enum'{p}'\""

MOD_ID = "Immersive Battle Fixes"
AUTHOR = "geoffjeffrey"
# (setting id, hover text, kind, provider variable, combo labels, default, MCM category, setter key, values)
# The setter key + value name the rootgraph node: ImmBF_Set_<key>_<value> (bool values lowercase). Defaults must match
# the GlobalVariablePrototypes patch (gen_patches.py) and the provider variables (setup_assets.py).
SETTINGS = [
    ("Granite fight: enemies",
     "The Granite fight at the Generators (every ending). Much fewer: 18 Granite instead of 41, one Gauss sniper instead "
     "of five. Fewer: 29. Vanilla: 39 (two generic Granite cannot come back). Takes effect the next time the fight starts.",
     "combo", "GraniteEnemies", ["Much fewer", "Fewer", "Vanilla"], 0, "Granite fight", "Granite_Enemies", [0, 1, 2]),
    ("Granite fight: no ambush",
     "On: the elite Granite stand visible in the arena instead of appearing out of nowhere, and the sniper has to spot "
     "you before he shoots. Off: as in vanilla. Takes effect the next time the fight starts.",
     "bool", "GraniteNoAmbush", None, True, "Granite fight", "Granite_NoAmbush", [True, False]),
]
P = "BP_MCM_ModExample1.BP_MCM_ModExample1:EventGraph."
HEADERS = {"/MCM_ModExample1/MCM_Header09.MCM_Header09": f"{RT}/T_ImmBF_MCMHeader.T_ImmBF_MCMHeader",
           "/MCM_ModExample1/MCM_CatHeader12.MCM_CatHeader12": f"{RT}/T_ImmBF_MCMCatHeader.T_ImmBF_MCMCatHeader"}
TYPES = {"bool": "NewEnumerator0", "combo": "NewEnumerator7"}
KIND = {"bool": ("bool", "BoolValue"), "combo": ("int", "ComboBoxSelectedOption")}

g = None
seq = [0]


def nm(kind):
    seq[0] += 1
    return f"{kind}_{900 + seq[0]}"


def exec_pins(n):
    n.pin("execute", "exec")
    n.pin("then", "exec", out=True)
    return n


def self_get(var, cat, x, y, self_cls, sub=None):
    n = Node(g, BG + "K2Node_VariableGet", nm("K2Node_VariableGet"), x, y, "", [f'VariableReference=(MemberName="{var}",bSelfContext=True)'])
    n.pin(var, cat, out=True, **({"sub": sub} if sub else {}))
    n.pin("self", "object", sub=self_cls, hidden=True, extra=TGT)
    return n


def self_set(var, cat, x, y, self_cls, comment="", default=None, sub=None):
    n = exec_pins(Node(g, BG + "K2Node_VariableSet", nm("K2Node_VariableSet"), x, y, comment, [f'VariableReference=(MemberName="{var}",bSelfContext=True)']))
    kw = {"sub": sub} if sub else {}
    n.pin(var, cat, extra=f'DefaultValue="{default}",' if default is not None else "", **kw)
    n.pin("Output_Get", cat, out=True, **kw)
    n.pin("self", "object", sub=self_cls, hidden=True, extra=TGT)
    return n


def branch(x, y, comment):
    n = exec_pins(Node(g, BG + "K2Node_IfThenElse", nm("K2Node_IfThenElse"), x, y, comment))
    n.pin("Condition", "bool", extra='DefaultValue="true",')
    n.pin("else", "exec", out=True)
    return n


def lib_pure(lib, libname, member, x, y, comment=""):
    n = Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x, y, comment,
             ["bIsPureFunc=True", f"FunctionReference=(MemberParent={lib},MemberName=\"{member}\")"])
    n.pin("self", "object", sub=lib, hidden=True, extra=f'DefaultObject="/Script/Engine.Default__{libname}",')
    return n


def lib_call(lib, default_obj, member, x, y, comment=""):
    n = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), x, y, comment,
                       [f"FunctionReference=(MemberParent={lib},MemberName=\"{member}\")"]))
    n.pin("self", "object", sub=lib, hidden=True, extra=f'DefaultObject="{default_obj}",')
    return n


# =================================================================================================================
# BP_ImmBFSubsystem
# =================================================================================================================
g = Graph()
g.box("EdGraphNode_Comment_900", -80, -120, 900, 300, "Enable tick (a ModWorldSubsystem ticks only when enabled)")
ev_i = Node(g, BG + "K2Node_Event", nm("K2Node_Event"), 0, 0, "",
            [f'EventReference=(MemberParent={MWS},MemberName="OnInitialized")', "bOverrideFunction=True"])
d = ev_i.pin("OutputDelegate", "delegate", out=True)
d.member_ref = f'MemberParent={MWS},MemberName="OnInitialized"'
ev_i.pin("then", "exec", out=True)
on = exec_pins(Node(g, BG + "K2Node_CallFunction", nm("K2Node_CallFunction"), 400, 0, "tick on",
                    ['FunctionReference=(MemberName="SetTickEnabled",bSelfContext=True)']))
on.pin("self", "object", sub=MWS, extra=TGT)
on.pin("bIsEnabled", "bool", extra='DefaultValue="true",')
g.link(ev_i["then"], on["execute"])

g.box("EdGraphNode_Comment_901", -80, 280, 3600, 700,
      "Spawn the MCM provider when MCM is installed (loaded by name: without MCM the class does not load, the mod plays with its defaults)")
ev_t = Node(g, BG + "K2Node_Event", nm("K2Node_Event"), 0, 400, "",
            [f'EventReference=(MemberParent={MWS},MemberName="OnTick")', "bOverrideFunction=True"])
d = ev_t.pin("OutputDelegate", "delegate", out=True)
d.member_ref = f'MemberParent={MWS},MemberName="OnTick"'
ev_t.pin("then", "exec", out=True)
ev_t.pin("DeltaTime", "real", subcat="float", out=True)
valid = lib_pure(KSL, "KismetSystemLibrary", "IsValid", 200, 600)
valid.pin("Object", "object", sub=OBJ)
valid.pin("ReturnValue", "bool", out=True)
g.link(self_get("Provider", "object", 0, 600, SUB_CLS, sub=ACTOR)["Provider"], valid["Object"])
b1 = branch(400, 400, "provider there?")
g.link(ev_t["then"], b1["execute"])
g.link(valid["ReturnValue"], b1["Condition"])
less = lib_pure(KML, "KismetMathLibrary", "Less_IntInt", 600, 600)
less.pin("A", "int", extra='DefaultValue="0",')
less.pin("B", "int", extra='DefaultValue="5",')
less.pin("ReturnValue", "bool", out=True)
g.link(self_get("SpawnAttempts", "int", 400, 650, SUB_CLS)["SpawnAttempts"], less["A"])
b2 = branch(750, 400, "fewer than 5 failed loads?")
g.link(b1["else"], b2["execute"])
g.link(less["ReturnValue"], b2["Condition"])
mkc = lib_pure(KSL, "KismetSystemLibrary", "MakeSoftClassPath", 800, 650)
mkc.pin("PathString", "string", extra=f'DefaultValue="{RT}/BP_ImmBFMCM.BP_ImmBFMCM_C",')
mkc.pin("ReturnValue", "struct", sub=SCPS, out=True)
cvc = lib_pure(KSL, "KismetSystemLibrary", "Conv_SoftClassPathToSoftClassRef", 1050, 650)
p_ = cvc.pin("SoftClassPath", "struct", sub=SCPS)
p_.ref = True
p_.const = True
cvc.pin("ReturnValue", "softclass", sub=OBJ, out=True)
g.link(mkc["ReturnValue"], cvc["SoftClassPath"])
ldc = lib_call(KSL, "/Script/Engine.Default__KismetSystemLibrary", "LoadClassAsset_Blocking", 1100, 400,
               "MCM provider class (loads only with MCM installed)")
ldc.pin("AssetClass", "softclass", sub=OBJ)
ldc.pin("ReturnValue", "class", sub=OBJ, out=True)
g.link(cvc["ReturnValue"], ldc["AssetClass"])
g.link(b2["then"], ldc["execute"])
vcl = lib_pure(KSL, "KismetSystemLibrary", "IsValidClass", 1350, 600)
vcl.pin("Class", "class", sub=OBJ)
vcl.pin("ReturnValue", "bool", out=True)
g.link(ldc["ReturnValue"], vcl["Class"])
b3 = branch(1500, 400, "loaded?")
g.link(ldc["then"], b3["execute"])
g.link(vcl["ReturnValue"], b3["Condition"])
# (ImmersiveLooting build 15: "Actor Class Reference is not compatible with Object Class Reference": cast the class)
ccast = exec_pins(Node(g, BG + "K2Node_ClassDynamicCast", nm("K2Node_ClassDynamicCast"), 1800, 400, "an actor class",
                       ["TargetType=" + ACTOR]))
ccast.pin("CastFailed", "exec", out=True)
ccast.pin("Class", "class", sub=OBJ)
ccast.pin("AsActor", "class", sub=ACTOR, out=True)
ccast.pin("bSuccess", "bool", out=True)
g.link(ldc["ReturnValue"], ccast["Class"])
g.link(b3["then"], ccast["execute"])
mkt = lib_pure(KML, "KismetMathLibrary", "MakeTransform", 1900, 650)
mkt.pin("Location", "struct", sub=VEC, extra='DefaultValue="0.000000,0.000000,0.000000",')
mkt.pin("Rotation", "struct", sub=ROT, extra='DefaultValue="0.000000,0.000000,0.000000",')
mkt.pin("Scale", "struct", sub=VEC, extra='DefaultValue="1.000000,1.000000,1.000000",')
mkt.pin("ReturnValue", "struct", sub=XFORM, out=True)
spm = exec_pins(Node(g, BG + "K2Node_SpawnActorFromClass", nm("K2Node_SpawnActorFromClass"), 2200, 400, "spawn the MCM provider"))
spm.pin("Class", "class", sub=ACTOR)
spm.pin("ReturnValue", "object", sub=ACTOR, out=True)
spm.pin("WorldContextObject", "object", sub=OBJ, hidden=True)
spm.pin("SpawnTransform", "struct", sub=XFORM)
spm.pin("CollisionHandlingOverride", "byte", sub=EN("/Script/Engine.ESpawnActorCollisionHandlingMethod"), extra='DefaultValue="AlwaysSpawn",')
spm.pin("TransformScaleMethod", "byte", sub=EN("/Script/Engine.ESpawnActorScaleMethod"), adv=True, extra='DefaultValue="MultiplyWithRoot",')
spm.pin("Owner", "object", sub=ACTOR, adv=True)
g.link(ccast["AsActor"], spm["Class"])
g.link(mkt["ReturnValue"], spm["SpawnTransform"])
g.link(ccast["then"], spm["execute"])
sp = self_set("Provider", "object", 2700, 400, SUB_CLS, "remember it", sub=ACTOR)
g.link(spm["then"], sp["execute"])
g.link(spm["ReturnValue"], sp["Provider"])
add = lib_pure(KML, "KismetMathLibrary", "Add_IntInt", 1800, 850)
add.pin("A", "int", extra='DefaultValue="0",')
add.pin("B", "int", extra='DefaultValue="1",')
add.pin("ReturnValue", "int", out=True)
g.link(self_get("SpawnAttempts", "int", 1600, 850, SUB_CLS)["SpawnAttempts"], add["A"])
sa = self_set("SpawnAttempts", "int", 2000, 750, SUB_CLS, "no MCM: count it (stop after 5)")
g.link(b3["else"], sa["execute"])
g.link(add["ReturnValue"], sa["SpawnAttempts"])


def emit(bp, lines, nodes):
    import json
    d = os.path.join(OUT, bp)
    os.makedirs(d, exist_ok=True)
    write(os.path.join(d, "EventGraph.txt"), lines)
    json.dump({"EventGraph": {"file": "EventGraph.txt", "nodes": nodes, "digest": page_digest(lines)}},
              open(os.path.join(d, "pages.json"), "w"), indent=1)


emit("BP_ImmBFSubsystem", g.text(), len(g.nodes))
print("subsystem:", len(g.nodes), "nodes")

# =================================================================================================================
# BP_ImmBFMCM
# =================================================================================================================
g = Graph()
seq[0] = 0


def defaults(values):
    def f(line):
        m = re.search(r'PinName="([^"]+)"', line) if "CustomProperties Pin" in line else None
        if m and m.group(1) in values:
            # the value where the editor writes it (after the pin type): placed right after PinName, an enum pin's
            # default (Type = the combo box) was reset on paste (ImmersiveLooting 1.3.1)
            v = values[m.group(1)]
            if re.search(r'(?<![A-Za-z])DefaultValue="[^"]*",', line):   # not AutogeneratedDefaultValue
                line = re.sub(r'(?<![A-Za-z])DefaultValue="[^"]*",', f'DefaultValue="{v}",', line, count=1)
            elif "bSerializeAsSinglePrecisionFloat=False," in line:
                line = line.replace("bSerializeAsSinglePrecisionFloat=False,", f'bSerializeAsSinglePrecisionFloat=False,DefaultValue="{v}",', 1)
            else:
                line = line.replace(f'PinName="{m.group(1)}",', f'PinName="{m.group(1)}",DefaultValue="{v}",', 1)
        return line
    return f


class _N:
    def __init__(self, name, pin_ids):
        self.name, self.pin_ids = name, pin_ids


class _P:
    def __init__(self, node_name, pid):
        self.node, self.id = _N(node_name, {}), pid


def xlink(lifted, lpin, gpin):
    """Link a lifted node's pin with a generated (bp_graph) pin, written on both ends."""
    gpin.links.append(_P(lifted.name, lifted.pin_ids[lpin]))
    lifted.links.setdefault(lpin, []).append((_N(gpin.node.name, {gpin.name: gpin.id}), gpin.name))


def make_str_array(x, y, labels, comment):
    n = Node(g, BG + "K2Node_MakeArray", nm("K2Node_MakeArray"), x, y, comment, [f"NumInputs={len(labels)}"])
    for k_, lab in enumerate(labels):
        n.pin(f"[{k_}]", "string", extra=f'DefaultValue="{lab}",')
    a = n.pin("Array", "string", out=True)
    a.container = "Array"
    return n


def opts_for(s, x, y):
    if s[2] == "combo":
        return make_str_array(x, y, s[4], "MCM: the dropdown's labels")["Array"]
    return make_str_array(x, y, [""], "MCM: always one empty string")["Array"]


def common(s):
    return {"ModID": MOD_ID, "AuthorName": AUTHOR, "Category": s[6], "SettingID": s[0], "SettingHoverText": s[1],
            "Type": TYPES[s[2]]}


lifted = []
# RegisterMCMSettings: each setting with its current value, then AddUniqueModID, Registered = true
ev_r = Lifted(EX, P + "K2Node_Event_6", "K2Node_Event_901", 0, 0)
lifted.append(ev_r)
prev, prev_pin = ev_r, "then"
for k, s in enumerate(SETTINGS):
    r = Lifted(EX, P + "K2Node_Message_55", f"K2Node_Message_{920 + k}", 700 + 300 * k, 0, defaults(common(s)))
    lifted.append(r)
    link(prev, prev_pin, r, "execute")
    link(ev_r, "BPI MCM API", r, "self")
    cat, vpin = KIND[s[2]]
    xlink(r, vpin, self_get(s[3], cat, 650 + 300 * k, 500, MCM_CLS)[s[3]])
    xlink(r, "ComboBoxOptions", opts_for(s, 650 + 300 * k, 650))
    prev, prev_pin = r, "then"
addid = Lifted(EX, P + "K2Node_Message_0", "K2Node_Message_902", 700 + 300 * len(SETTINGS), 0, defaults({"ModID": MOD_ID}))
lifted.append(addid)
link(prev, prev_pin, addid, "execute")
link(ev_r, "BPI MCM API", addid, "self")
sr = self_set("Registered", "bool", 1000 + 300 * len(SETTINGS), 0, MCM_CLS, "registered (Apply may read now)", default="true")
xlink(addid, "then", sr["execute"])

# RegisterMCMDefaultSettings
ev_d = Lifted(EX, P + "K2Node_Event_9", "K2Node_Event_902", 0, 1300)
lifted.append(ev_d)
prev, prev_pin = ev_d, "then"
for k, s in enumerate(SETTINGS):
    vals = common(s)
    if s[2] == "combo":
        vals["ComboBoxSelectedOption"] = str(s[5])
    else:
        vals["BoolValue"] = "true" if s[5] else "false"
    dn = Lifted(EX, P + "K2Node_Message_31", f"K2Node_Message_{930 + k}", 700 + 400 * k, 1300, defaults(vals))
    lifted.append(dn)
    link(prev, prev_pin, dn, "execute")
    link(ev_d, "BPI MCM API", dn, "self")
    xlink(dn, "ComboBoxOptions", opts_for(s, 350 + 400 * k, 1950))
    prev, prev_pin = dn, "then"

# ApplyMCMSettings: (only once registered) read each setting into its variable, then start its setter node
ev_a = Lifted(EX, P + "K2Node_Event_7", "K2Node_Event_903", 0, 2600)
lifted.append(ev_a)
br = branch(350, 2600, "registered? (else another mod's click reads our settings as false / 0)")
xlink(ev_a, "then", br["execute"])
g.link(self_get("Registered", "bool", 150, 2800, MCM_CLS)["Registered"], br["Condition"])
prev_exec = [br["then"]]
for k, s in enumerate(SETTINGS):
    gt = Lifted(EX, P + "K2Node_Message_66", f"K2Node_Message_{940 + k}", 700, 2600 + 300 * k,
                defaults({"ModID": MOD_ID, "SettingID": s[0]}))
    lifted.append(gt)
    for p_ in prev_exec:
        xlink(gt, "execute", p_)
    link(ev_a, "BPI MCM API", gt, "self")
    cat, vpin = KIND[s[2]]
    st = self_set(s[3], cat, 1250, 2600 + 300 * k, MCM_CLS, f"the setting {s[0]!r}")
    xlink(gt, "then", st["execute"])
    xlink(gt, vpin, st[s[3]])
    prev_exec = [st["then"]]


def setter(sid, x, y, ins):
    """StartQuestNode(sid) then the console twin; returns the last exec out."""
    q = lib_call(CPP, "/Script/Stalker2.Default__CppMediator", "StartQuestNode", x, y, f"setter {sid}")
    q.pin("SID", "struct", sub=SID_T, extra=f'DefaultValue="(Value=\\"{sid}\\")",')
    for p_ in ins:
        g.link(p_, q["execute"])
    c = lib_call(KSL, "/Script/Engine.Default__KismetSystemLibrary", "ExecuteConsoleCommand", x + 400, y, "the same by console (twin)")
    c.pin("WorldContextObject", "object", sub=OBJ, hidden=True)
    c.pin("Command", "string", extra=f'DefaultValue="XStartQuestNodeBySID {sid}",')
    c.pin("SpecificPlayer", "object", sub=PC_CLS, adv=True)
    g.link(q["then"], c["execute"])
    return c["then"]


X, Y = 1700, 2600
for k, s in enumerate(SETTINGS):
    y = Y + 500 * k
    if s[2] == "bool":
        b = branch(X, y, f"{s[0]}: on?")
        for p_ in prev_exec:
            g.link(p_, b["execute"])
        g.link(self_get(s[3], "bool", X - 200, y + 150, MCM_CLS)[s[3]], b["Condition"])
        prev_exec = [setter(f"ImmBF_Set_{s[7]}_true", X + 300, y, [b["then"]]),
                     setter(f"ImmBF_Set_{s[7]}_false", X + 300, y + 200, [b["else"]])]
    else:
        outs, ins, x = [], prev_exec, X
        for i, v in enumerate(s[8]):
            sid = f"ImmBF_Set_{s[7]}_{v}"
            if i == len(s[8]) - 1:   # the last value: no test left
                outs.append(setter(sid, x, y, ins))
                break
            eq = lib_pure(KML, "KismetMathLibrary", "EqualEqual_IntInt", x - 200, y + 150)
            eq.pin("A", "int", extra='DefaultValue="0",')
            eq.pin("B", "int", extra=f'DefaultValue="{v}",')
            eq.pin("ReturnValue", "bool", out=True)
            g.link(self_get(s[3], "int", x - 400, y + 150, MCM_CLS)[s[3]], eq["A"])
            b = branch(x, y, f"{s[0]} = {s[4][i]}?")
            for p_ in ins:
                g.link(p_, b["execute"])
            g.link(eq["ReturnValue"], b["Condition"])
            outs.append(setter(sid, x + 300, y + 200, [b["then"]]))
            ins, x = [b["else"]], x + 1200
        prev_exec = outs

out = []
for l_ in lifted:
    out += l_.text()
out += g.text()
for a_, b_ in HEADERS.items():
    out = [l_.replace(a_, b_) for l_ in out]
assert not any("/MCM_ModExample1/" in l_ for l_ in out)


def sid_default_where_the_editor_writes_it(line):
    # a struct pin's default goes after the pin type, where the editor writes it (an enum pin default placed right
    # after PinName was reset on paste, ImmersiveLooting 1.3.1; strings were fine)
    m = re.search(r'PinName="SID",(DefaultValue="(?:[^"\\]|\\.)*",)', line)
    if not m:
        return line
    line = line.replace(m.group(1), "", 1)
    return line.replace("bSerializeAsSinglePrecisionFloat=False,", "bSerializeAsSinglePrecisionFloat=False," + m.group(1), 1)


out = [sid_default_where_the_editor_writes_it(l_) for l_ in out]
emit("BP_ImmBFMCM", out, len(g.nodes) + len(lifted))
print("provider:", len(g.nodes) + len(lifted), "nodes")
