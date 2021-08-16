# Changelog
Notable changes to DER-VET are documented in this CHANGELOG.md.

Questions and feedback can be submitted to the Electric Power Research Institute (EPRI) from the Survey Monkey feedback linked on the StorageVET website (https://www.storagevet.com/).

The format is based on [Keep a Changelog] (https://keepachangelog.com/en/1.0.0/).

## [1.1.1] - 2021-07-09 to 2021-08-03
### Fixed
- Removed comma from soc_target description in the Model Parameters CSV

## [1.1.0] - 2021-04-14 to 2021-07-09
### Added
- this CHANGELOG.md file
- useful error messaging and warning for extreme soc_target values with reliability
- all growth rates have a minimum value of -100 percent
- Fleet EV will output the Baseline Load time series

### Changed
- description of battery soc_target updated for reliability based ES sizing
- modified the README.md with better and more thorough instructions for Installation
- increased the max limit (hours) on optimization window to be 8784

### Fixed
- corrected the logic and docstrings in ParamsDER class bad_active_combo method
- load_technology bug regarding names_list was fixed
