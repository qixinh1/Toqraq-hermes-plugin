# Engine Support Gates

This document records the current external evidence required before an engine
can enter Toqraq's selectable catalog. It is a support-status record, not legal
advice and not a substitute for written vendor authorization. Product support
still requires the complete technical evidence in [testing.md](testing.md).

Evidence was reviewed on 2026-08-07. Vendor terms and installer behavior are
release inputs and must be rechecked before implementing or publishing a new
engine contribution.

## Admission rule

An engine/version is selectable only when all of these are true:

- Toqraq has a documented right to use, integrate, and distribute every
  required editor, bridge, plugin, and installer artifact;
- the exact version can be provisioned into an isolated Toqraq-managed path
  through an official mechanism;
- required login, license, or terms are explicit user actions in Hermes;
- instrumentation uses an official extension boundary and does not silently
  edit project source, configuration, or dependencies;
- the complete common capability, clean-install, preview, and cleanup suite
  passes on the target platform and architecture.

Failure of one gate means no catalog record, setup choice, `supported` label,
or reduced adapter. Common architecture remains extensible without exposing an
unfinished engine.

## Current status

| Engine | Current decision | Blocking evidence |
| --- | --- | --- |
| Godot | Windows 4.7.1 native candidate verified; deterministic package workflow implemented but not yet evidenced; not selectable | run, publish, and admit the exact digest-pinned component, then pass clean-store, standard-install, and interactive Desktop gates |
| Unity | blocked; do not implement or register | obtain applicable Authorized Agentic Access and prior written Unity authorization, then validate an official isolated installation and instrumentation path |
| Unreal Engine | gated research; do not register | confirm official installation and Engine Plugin distribution rights, account/EULA flow, and complete real-engine baseline |
| Cocos Creator | gated research; do not register | prove a supported external/global extension loading contract for each version and confirm integration and redistribution rights |

## Godot

### Official facts

Godot supports C++ custom modules supplied outside the upstream source tree
through SCons `custom_modules`. Such a module requires an engine rebuild and
can access deeper engine APIs than GDExtension. Godot also exposes a `--wid`
launch option for native window embedding and separate headless modes for
import or non-visual work. Godot is MIT-licensed and permits redistribution
with its notices.

Sources:

- [Custom modules in C++](https://docs.godotengine.org/en/4.4/contributing/development/core_and_modules/custom_modules_in_cpp.html)
- [Godot build system](https://docs.godotengine.org/en/stable/engine_details/development/compiling/introduction_to_the_buildsystem.html)
- [Command-line tutorial](https://docs.godotengine.org/en/latest/tutorials/editor/command_line_tutorial.html)
- [Godot license](https://github.com/godotengine/godot/blob/master/LICENSE.txt)

### Toqraq decision

CI checks out an exact untouched upstream tag and supplies
`engine/godot/modules/toqraq` as an external custom module. It builds the
editor runtime, records all inputs and notices, and publishes a managed
immutable component only after conformance.
The plugin never scans for or modifies a user Godot installation.

The module translates Godot APIs directly into the authenticated common
Bridge and installs no project `addons/` plugin. Visual play uses the native
display path; headless mode is limited to import, analysis, and tests. The
repository records an earlier local 4.7.1 observation covering its focused
native suite and production host-adapter exercise, but no published component
record exists and the production catalog remains empty. The repository's
deterministic package and strict verification path has synthetic tamper
evidence only; it has not yet produced a recorded real 4.7.1 candidate ZIP from
the manual workflow.

## Unity

### Official facts

Unity's current Terms of Service describe AI agents, LLMs, MCPs, and CLIs as
agentic access and require Unity-authorized access. The same section requires
prior written authorization for a plugin, extension, or integration that
interfaces with Unity offerings. This is an admission gate, not a technical
warning that user login alone resolves.

Unity supplies an experimental Unity CLI for exact editor/module installation.
Personal license activation remains a Hub user action. UPM packages and Unity Pipeline expose
substantial editor
automation, but they are project dependencies and may recompile the project.

Sources:

- [Unity Terms of Service](https://unity.com/legal/terms-of-service)
- [Unity CLI](https://docs.unity.com/en-us/unity-cli/use-unity-cli)
- [License activation methods](https://docs.unity3d.com/cn/6000.0/Manual/LicenseActivationMethods.html)
- [Unity Pipeline package](https://docs.unity.com/en-us/unity-production-pipeline/local-tools-cli/unity-pipeline-package)

### Toqraq decision

No Unity package, installer, bridge, catalog record, or `supported` UI is
implemented until the project has the required written authorization and
agentic-access route. If unblocked, the adapter must prefer the supported
official automation surface, install the exact editor into a managed path, and
make any project package change visible and consented through Hermes. Toqraq
does not redistribute the Unity Editor or infer permission from a user's
license activation.

## Unreal Engine

### Official facts

Unreal supports Engine Plugins below an engine installation and Project
Plugins below a project. BuildGraph can produce an Installed Build from
authorized source. Official binary installation is primarily an Epic Games
Launcher flow, while source access requires linked authorized accounts and
EULA acceptance. Engine Code and Engine Tools distribution are restricted by
the Unreal EULA.

Remote Control, Automation, and Trace/Insights are useful official facilities,
but Remote Control is documented as Beta and is not itself Toqraq's stable
cross-engine bridge.

Sources:

- [Plugins in Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/plugins-in-unreal-engine)
- [Installing Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/installing-and-setting-up-a-project)
- [Downloading source](https://dev.epicgames.com/documentation/unreal-engine/downloading-source-code-in-unreal-engine)
- [BuildGraph](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-use-buildgraph-for-unreal-engine)
- [Unreal Engine EULA](https://www.unrealengine.com/eula/unreal)

### Toqraq decision

The preferred technical form, if distribution review permits it, is a
versioned Engine Plugin installed only into a Toqraq-managed exact engine root.
The default provisioning experience is an explicit Hermes-guided official
Launcher/account/EULA flow followed by exact local verification. A source
BuildGraph provider would be a separate advanced choice because of its size,
toolchain, account, and time cost.

No prebuilt bridge or support claim ships until its distribution channel and
license obligations are reviewed for the exact artifact and the complete
baseline passes.

## Cocos Creator

### Official facts

Cocos Creator extensions use main, panel, Scene Script, and message-system
surfaces capable of deep editor and scene integration. Browser Preview is a
strong candidate for a Hermes `WebSurface`. Current 3.8 documentation is not
clear enough to prove a stable project-external automatic extension path: the
Extension Manager describes copying or linking into project `extensions`,
while another page refers to project and global extensions. Command-line build
also requires a GUI environment.

The open-source Cocos runtime engine is MIT, but the Creator Editor is a
separate proprietary product; the runtime license does not authorize editor
redistribution or integration.

Sources:

- [Extension infrastructure](https://docs.cocos.com/creator/3.8/manual/en/editor/extension/package.html)
- [Extension Manager](https://docs.cocos.com/creator/3.8/manual/en/editor/extension/extension-manager.html)
- [Editor main menu](https://docs.cocos.com/creator/3.8/manual/en/editor/mainMenu/index.html)
- [Preview](https://docs.cocos.com/creator/3.8/manual/en/editor/preview/)
- [Cocos user agreement](https://download.cocos.com/CocosUdc/agreement/Cocos_User_Service_Agreement_en_20220901.html)

### Toqraq decision

Before implementation, a version-specific spike must prove that a managed
external extension can load, enable, communicate, and unload without a silent
project mutation. Legal review or written vendor confirmation must cover the
planned integration and any distributed extension. Until both gates close,
Cocos remains absent from the selectable catalog.

If admitted, browser preview is the preferred `WebSurface`; the extension maps
Scene Script and editor messages to the common bridge without exposing Cocos
objects to shared services.

## Revalidation

Every engine-support change records:

- official terms and documentation URLs plus review date;
- exact authorized acquisition and extension mechanism;
- artifacts Toqraq may or may not redistribute;
- login, license, and user-action states shown by setup;
- versions, platforms, and architectures actually tested;
- clean-store conformance and interactive evidence;
- the person or written vendor record approving a previously blocked gate.

A documentation change alone never changes support status. The catalog record
and its passing evidence are the executable support claim.
