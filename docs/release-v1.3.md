# LACMC v1.3 evaluation-only deployment

The current v1.3 release replaces the earlier full-project image with an evaluation-only image. Download all lacmc-qmix-1.3-eval-only.tar.part-NNN parts listed in release-manifest.json, verify SHA256SUMS, and load lacmc-qmix:1.3 with scripts/load_image.py. The existing Windows/Linux evaluation launch commands are unchanged.

The final image contains 19 project runtime files. Training entry points and methods, Q-learning/mixer training machinery, relation/trajectory training modules, replay sampling and normalization, plotting, alternate environments, backup files, and unused project files are excluded. A fresh final stage copies dependencies and only the approved runtime files; the saved archive is audited across every layer to detect unintended project source.

models.tar.gz now contains only results/agent/model-mac_0.pt and results/adapter/adapter_1.pt through adapter_9.pt. These ten checkpoint files are byte-identical to the originals. The ten experiment maps and Python dependency versions are unchanged. The manifest records the current build provenance, package versions, per-runtime-file hashes, and original image provenance.

Validation completed locally on GPU: ten maps times 32 episodes, plus a fixed-input comparison of Q values and actions on all ten tasks with maximum absolute Q difference 0.0. The cloud build verifies its runtime hashes against the locally validated source and checks that dependency versions are unchanged. These checks do not guarantee identical success rates across runs or hardware. Reward-based success classification remains unchanged.

Existing users must refresh SHA256SUMS, release-manifest.json, models.tar.gz, and all new image parts. Old cmac-dtr-1.3.tar.part-* files belong to the previous image. Do not mix the old and new bundles. Loading the current image replaces the local lacmc-qmix:1.3 tag.

The repository's original LICENSE and src/requirements.txt remain unchanged. Required evaluation source is still readable and extractable. This release reduces disclosure; it is not encrypted and cannot revoke previously downloaded copies. Obtain SC2 Linux 4.10 separately from Blizzard after accepting its license.
