CHANGELOG
---------

Notable changes to this project will be documented in this file.
The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`__.

Latest changes
--------------

* Project foundation and scaffolding were established, including the initial repository setup and template alignment.
* Update to support data pipeline, imports JSON files from UDL and outputs to CDF with ISTP-compliant metadata.
* Runtime and reliability improvements included temporary-path handling, logging improvements, and threaded UDL download support.
* Developer experience was improved through dependency updates, NumPy/doctest constraint refinements, formatting/test updates, and devcontainer/workflow maintenance.
* Documentation and release-readiness work expanded substantially, including docstring updates, Read the Docs/DOI integration, and new customization/changelog documentation.
* Updated docs build behavior to run Sphinx via the active Python environment (``python -m sphinx``) to avoid Homebrew executable conflicts.
* Fixed README badge definitions and URLs (GitHub Actions org links and coverage badge reStructuredText syntax).
* Added package version display to the About page using the Sphinx ``|release|`` substitution.
* Improved changelog discoverability from the docs landing page with a direct link.
