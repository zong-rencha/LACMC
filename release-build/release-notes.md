# LACMC v1.3: evaluation-only Docker image

This release now contains an evaluation-only image for `python -u evaluate3.py`. The previously published full-project image has been replaced.

- `lacmc-qmix-1.3-eval-only.tar.part-NNN`: all parts of the same gzip-compressed Docker archive; loads as `lacmc-qmix:1.3`.
- `models.tar.gz`: only the 10 checkpoint files required for evaluation. Each retained checkpoint is byte-identical to the original release.
- `maps.tar.gz`: the same ten experiment maps.
- `release-manifest.json` and `SHA256SUMS`: new image and asset checksums, environment package versions, and the 19-file runtime inventory.

Removed project content includes training entry points and training methods, Q-learning/mixer training machinery, relation/trajectory training modules, replay sampling and normalization, plotting helpers, alternate environments, backup files, and unused checkpoints. The final image is built from a fresh base stage; all archived image layers are audited so deleted project source cannot remain in old layers. Python dependency versions are preserved.

Validation: local GPU evaluation completed all 10 maps with 32 episodes each; fixed-input Q values and selected actions matched the original implementation exactly across all ten tasks (maximum absolute Q error 0.0). The cloud build verifies that its 19 runtime files match the locally validated file hashes and that Python package versions are unchanged. This does not guarantee identical success rates across runs or hardware; reward-based success classification remains unchanged.

Use the current repository README and download scripts. Refresh the checksums, manifest, image parts, and model archive; do not mix old and new release assets. Loading the new image replaces the local `lacmc-qmix:1.3` tag. GitHub's two automatic "Source code" links contain deployment files, not the Docker image.

Blizzard SC2 Linux 4.10 is installed separately after accepting its license. Necessary evaluation source remains readable and extractable; this release reduces exposed content and is not encrypted. Previously downloaded old images cannot be recalled.
