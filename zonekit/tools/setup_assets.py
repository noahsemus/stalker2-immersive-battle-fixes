"""Creates ImmersiveBattleFixes' Blueprint assets except their event graphs (those are pasted: gen_mcm.py) and the
MCM header pictures. Runs in the open editor (harness ue_exec) or headless (run_headless.ps1); re-running keeps
existing assets and only adds what is missing.

- /ImmersiveBattleFixes/Runtime/BP_ImmBFSubsystem (ModWorldSubsystem): spawns the MCM provider when MCM is installed.
- /ImmersiveBattleFixes/Runtime/BP_ImmBFMCM (Actor): the MCM settings provider. The interface
  /ModConfigurationMenu/BPI_MCM_SettingsProvider is added by hand (Class Settings > Interfaces; Python cannot).
- T_ImmBF_MCMHeader / T_ImmBF_MCMCatHeader: copies of MCM_ModExample1's header pictures (MCM does not ship the
  example's own: a mod pointing at them shows a white box behind white text, ImmersiveLooting 1.1.0).
Log: <SCRATCH>/setup_assets.log
"""
import os
import traceback
import unreal

RT = f"{MOD_ROOT}/Runtime"
SUBSYS = f"{RT}/BP_ImmBFSubsystem"
MCMBP = f"{RT}/BP_ImmBFMCM"
HEADERS = {"/MCM_ModExample1/MCM_Header09": f"{RT}/T_ImmBF_MCMHeader",
           "/MCM_ModExample1/MCM_CatHeader12": f"{RT}/T_ImmBF_MCMCatHeader"}
EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary
LOG = os.path.join(SCRATCH, "setup_assets.log")
lines = []

# provider variables: the setting values (defaults = the mod's defaults, the same as the GlobalVariablePrototypes
# patch written by gen_patches.py) and Registered (Apply waits for it: an unknown setting reads as false / 0)
import json
_settings = json.load(open(os.path.join(REPO, "zonekit", "tools", "mcm_settings.json"), encoding="utf-8"))
MCM_VARS = [("Registered", "bool", None)] + [(s["var"], "int" if s["kind"] == "combo" else "bool", s["default"]) for s in _settings]


def log(s):
    lines.append(str(s)); unreal.log("[harness] " + str(s))


def mount(uplugin, root, asset):
    if not EAL.does_asset_exist(f"{root}/{asset}"):
        try:
            unreal.GameFeaturesSubsystem.load_and_activate_game_feature_plugin(
                "file:" + os.path.abspath(uplugin).replace("\\", "/"), unreal.GameFeaturePluginLoadComplete())
        except Exception as e:
            log(f"load_and_activate {uplugin} failed: {e}")
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([root], True)
    ok = EAL.does_asset_exist(f"{root}/{asset}")
    log(f"mounted {root}: {ok}")
    return ok


def make_bp(path, parent):
    if EAL.does_asset_exist(path):
        return unreal.load_asset(path)
    f = unreal.BlueprintFactory()
    f.set_editor_property("parent_class", parent)
    folder, name = path.rsplit("/", 1)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.Blueprint, f)
    log(f"created {path}: {bp}")
    return bp


def T(kind):
    if kind in ("bool", "int", "real", "string"):
        return BEL.get_basic_type_by_name(kind)
    return BEL.get_object_reference_type(kind)


def add_vars(bp, path, vars_):
    BEL.compile_blueprint(bp)
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    for name, kind, default in vars_:
        try:
            cdo.get_editor_property(name)
            continue
        except Exception:
            pass
        log(f"{path}: add {name} -> {BEL.add_member_variable(bp, name, T(kind))}")
    BEL.compile_blueprint(bp)
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    for name, kind, default in vars_:
        if default is not None:
            cdo.set_editor_property(name, default)
        log(f"{path}: {name} = {cdo.get_editor_property(name)!r}")
    log(f"{path} saved: {EAL.save_asset(path, only_if_is_dirty=False)}")


try:
    mods = os.path.dirname(os.path.dirname(os.path.abspath(UPLUGIN)))
    mount(UPLUGIN, MOD_ROOT, MOD)
    mount(os.path.join(mods, "ModConfigurationMenu", "ModConfigurationMenu.uplugin"), "/ModConfigurationMenu", "BPI_MCM_SettingsProvider")
    mount(os.path.join(mods, "MCM_ModExample1", "MCM_ModExample1.uplugin"), "/MCM_ModExample1", "BP_MCM_ModExample1")
    for src, dst in HEADERS.items():
        if not EAL.does_asset_exist(dst):
            log(f"duplicate {src} -> {dst}: {EAL.duplicate_asset(src, dst)}")
        log(f"{dst}: {EAL.does_asset_exist(dst)} saved {EAL.save_asset(dst, only_if_is_dirty=False)}")
    mcm = make_bp(MCMBP, unreal.Actor)
    add_vars(mcm, MCMBP, MCM_VARS)
    sub = make_bp(SUBSYS, unreal.ModWorldSubsystem)
    add_vars(sub, SUBSYS, [("Provider", unreal.Actor.static_class(), None), ("SpawnAttempts", "int", None)])
    for p in (SUBSYS, MCMBP, *HEADERS.values()):
        log(f"verify {p}: {EAL.does_asset_exist(p)}")
except Exception:
    log("EXCEPTION: " + traceback.format_exc())
os.makedirs(SCRATCH, exist_ok=True)
open(LOG, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
