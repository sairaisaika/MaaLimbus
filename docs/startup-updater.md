# Software startup updater

Use the desktop MaaLimbus shortcut, which points to
`launcher/MaaLimbusLauncher.exe`. The launcher copies its own frozen bundle to
a unique sibling directory and exits. That copied process waits for its known
parent to exit, checks CIM identity and the shared controller lease, checks the
official GitHub stable release, validates the download and installs before
opening the unmodified native MXU. Any normal Windows UAC request belongs to MXU.

The global GitHub automatic updates selector takes effect on the next launch.
Default is enabled. Directly opening MaaLimbus.exe opens MXU without this check.
MXU 2.7.1's built-in updater treats versions below 1.0 as debug projects, so its
built-in update check is insufficient for this v0.1.0 project.

Rate-limit deadlines, ETags and release metadata remain in the private
`config/user-update-state.json`. Network failure and deferred downloads continue
with the installed version. Unknown settings, package validation failure and
unresolved installation state stop before opening the app. A verified rollback
can reopen the restored version. `build/startup-update-result.json` records the
actual installed metadata; it is not evidence of a visibly opened GUI.

The named controller.lock now resolves to one LocalAppData/MaaLimbus lock across
source CLI, packaged Agent and updater, independent of their different roots.
The updater runs outside the install directory; its own CIM entry is the only
entry excluded from the closed-app check. All game and GUI/Agent entries retain
their normal exclusion. No process is terminated to make an install possible.

Unit tests verify deferred checks, native disabled setting, newer-only selection,
installed metadata, rollback and ambiguous failure. Public Release download,
desktop shortcut launch and visible new-version restart require actual evidence
and remain separate acceptance items until performed.
