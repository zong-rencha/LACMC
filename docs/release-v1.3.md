# LACMC v1.3 evaluation deployment

Use the prebuilt lacmc-qmix:1.3 image with the model and map assets from this repository's v1.3 Release. scripts/download_assets.py verifies and prepares the files; scripts/load_image.py loads the image; scripts/run-evaluation.sh or scripts/run-evaluation.ps1 starts evaluate3.py inside the image.

The eight Release assets were copied byte-for-byte from a release accidentally published to a different repository. The four image parts retain their cmac-dtr-1.3.tar.part-NNN names so the existing checksums and manifest remain valid. No image, model, or map was rebuilt or changed. The manifest records the original build provenance; its old repository or commit references do not identify the current deployment scripts.

Host-side research source and build files are not required for evaluation. This repository preserves its original LICENSE and src/requirements.txt. The existing image still contains extractable research source; distributing it is not a source confidentiality measure.
