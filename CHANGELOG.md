# Changelog

This project uses [towncrier](https://towncrier.readthedocs.io/) and the
changes for the upcoming release can be found in
<https://github.com/ansys/openapi-common/tree/main/doc/changelog.d/>.

<!-- towncrier release notes start -->

## [2.2.1](https://github.com/ansys/openapi-common/releases/tag/v2.2.1) - March 24, 2025


### Fixed

- Relax validation on enum values deserialization [#755](https://github.com/ansys/openapi-common/pull/755)


### Maintenance

- Update Copyright Year in License Headers [#729](https://github.com/ansys/openapi-common/pull/729)
- Prepare patch release 2.2.1 [#758](https://github.com/ansys/openapi-common/pull/758)

## [2.2.0](https://github.com/ansys/openapi-common/releases/tag/v2.2.0) - 2024-10-25


### Added

- Add support for Python 3.13 [#684](https://github.com/ansys/openapi-common/pull/684)


### Fixed

- Add missing required inputs for v8 ansys/actions [#685](https://github.com/ansys/openapi-common/pull/685)


### Dependencies

- Drop support for Python 3.9 [#674](https://github.com/ansys/openapi-common/pull/674)


### Documentation

- Update Repository URL in pyproject.toml [#665](https://github.com/ansys/openapi-common/pull/665)
- Add a documentation note about pip-system-certs [#696](https://github.com/ansys/openapi-common/pull/696)


### Maintenance

- Fix GitHub Actions syntax for doc-deploy-changelog action [#648](https://github.com/ansys/openapi-common/pull/648)
- chore: update CHANGELOG for v2.1.1 [#658](https://github.com/ansys/openapi-common/pull/658)
- Update CONTRIBUTORS and AUTHORS to new format [#679](https://github.com/ansys/openapi-common/pull/679)
- Prepare 2.2 Release [#697](https://github.com/ansys/openapi-common/pull/697)

## [2.1.1](https://github.com/ansys/openapi-common/releases/tag/v2.1.1) - 2024-08-26


### Fixed

- Allow packages to build documentation if they inherit classes in this package [#651](https://github.com/ansys/openapi-common/pull/651)


### Documentation

- Prepare 2.1.1 release [#657](https://github.com/ansys/openapi-common/pull/657)

## [2.1.0](https://github.com/ansys/openapi-common/releases/tag/v2.1.0) - 2024-08-21


### Added

- Allow authentication scheme to be specified explicitly when connecting with credentials [#638](https://github.com/ansys/openapi-common/pull/638)


### Changed

- 548 - CI - Add doc-changelog action [#563](https://github.com/ansys/openapi-common/pull/563)
- CI - 574 - Update codecov action to v4 [#575](https://github.com/ansys/openapi-common/pull/575)
- Manually update changelog for 2.0.0 and 2.0.1 releases [#576](https://github.com/ansys/openapi-common/pull/576)
- Update CNAME to support publishing documentation from this repository [#577](https://github.com/ansys/openapi-common/pull/577)
- Bump version to 2.1.0 [#578](https://github.com/ansys/openapi-common/pull/578)
- Remove documentation build parallel execution arguments [#580](https://github.com/ansys/openapi-common/pull/580)
- Fix labelling workflow [#581](https://github.com/ansys/openapi-common/pull/581)
- Don't generate changelog fragments for dependabot PRs [#587](https://github.com/ansys/openapi-common/pull/587)
- Update changelog for 2.0.2 release [#588](https://github.com/ansys/openapi-common/pull/588)


### Fixed

- Support requests-auth 8.0.0 [#640](https://github.com/ansys/openapi-common/pull/640)


### Dependencies

- Use ansys standard actions [#555](https://github.com/ansys/openapi-common/pull/555)
- Bump fastapi from 0.110.2 to 0.111.0 [#583](https://github.com/ansys/openapi-common/pull/583)
- Bump ansys/actions from 5 to 6 [#584](https://github.com/ansys/openapi-common/pull/584)
- Bump jinja2 from 3.1.3 to 3.1.4 [#585](https://github.com/ansys/openapi-common/pull/585)


### Documentation

- Add versionadded directives for new functionality [#647](https://github.com/ansys/openapi-common/pull/647)


### Maintenance

- Fix labeller workflow [#634](https://github.com/ansys/openapi-common/pull/634)
- Use PyPI Trusted Publisher approach for releases [#646](https://github.com/ansys/openapi-common/pull/646)

## openapi-common 2.0.2, 2024-05-03

### New features

* [Issue #549](https://github.com/ansys/openapi-common/issues/459),
  [Pull request #555](https://github.com/ansys/openapi-common/pull/555):
  Use Ansys standard actions.

### Documentation

* [Issue #494](https://github.com/ansys/openapi-common/issues/494),
  [Pull request #577](https://github.com/ansys/openapi-common/pull/577):
  Support multi-versioned documentation.

### Contributors

* Ludovic Steinbach (Ansys)

## openapi-common 2.0.1, 2024-05-02

### Bugs fixed

* [Issue #570](https://github.com/ansys/openapi-common/issues/570),
  [Pull request #571](https://github.com/ansys/openapi-common/pull/571):
  Add handling for authority URLs with no trailing slash.

### Contributors

* Doug Addy (Ansys)

## openapi-common 2.0.0, 2024-03-01

### New features

* [Issue #495](https://github.com/ansys/openapi-common/issues/495),
  [Pull request #497](https://github.com/ansys/openapi-common/pull/497):
  Support optional fields in models.
* [Issue #508](https://github.com/ansys/openapi-common/issues/508),
  [Pull request #514](https://github.com/ansys/openapi-common/pull/514):
  Add `Unset` `__repr__`.

### Contributors

* Doug Addy (Ansys)
* Andy Grigg (Ansys)
* Ludovic Steinbach (Ansys)

## openapi-common 1.5.1, 2024-03-01

### New features

* [Issue #491](https://github.com/ansys/openapi-common/issues/491),
  [Pull request #434](https://github.com/ansys/openapi-common/pull/434):
  Add `py.typed` file to release.
* [Issue #482](https://github.com/ansys/openapi-common/issues/482),
  [Pull request #469](https://github.com/ansys/openapi-common/pull/469):
  Support deserialization of partially or undefined models.

### Contributors

* Doug Addy (Ansys)
* Andy Grigg (Ansys)
* Ludovic Steinbach (Ansys)

## openapi-common 1.4.0, 2024-01-10

### New features

* [Pull request #451](https://github.com/ansys/openapi-common/pull/451):
  Move some auto-generated model methods to the base class.

### Bugs fixed

* [Issue #443](https://github.com/ansys/openapi-common/issues/443),
  [Pull request #447](https://github.com/ansys/openapi-common/pull/447):
  `Enum` deserialization now properly instantiates the `Enum`.

### Documentation

* [Pull request #457](https://github.com/ansys/openapi-common/pull/457):
  Fix Ubuntu 20.04 installation instructions.

### Contributors

* Doug Addy (Ansys)
* Andy Grigg (Ansys)
* Ludovic Steinbach (Ansys)

## openapi-common 1.3.0, 2023-11-13

### New features

* [Issue #311](https://github.com/ansys/openapi-common/issues/311),
  [Pull request #312](https://github.com/ansys/openapi-common/pull/312):
  Support response type to status code mapping for response deserialization.

### Bugs fixed

* [Issue #313](https://github.com/ansys/openapi-common/issues/313),
  [Pull request #316](https://github.com/ansys/openapi-common/pull/316):
  Improve `ApiConnectionException` error message.
* [Issue #380](https://github.com/ansys/openapi-common/issues/380),
  [Pull request #381](https://github.com/ansys/openapi-common/pull/381):
  Improve regular expression performance while deserializing response.

### Miscellaneous

* [Pull request #347](https://github.com/ansys/openapi-common/pull/347):
  Drop support for Python 3.7.
* [Pull request #432](https://github.com/ansys/openapi-common/pull/432):
  Drop support for Python 3.8.

### Contributors

* Doug Addy (Ansys)
* Andy Grigg (Ansys)
* Ludovic Steinbach (Ansys)

## openapi-common 1.2.2, 2023-04-14

### Bugs fixed

* [Issue #380](https://github.com/ansys/openapi-common/issues/380),
  [Pull request #381](https://github.com/ansys/openapi-common/pull/381):
  Improve regular expression performance while deserializing response.

### Contributors

* Doug Addy (Ansys)

## openapi-common 1.2.1, 2023-02-20

### New features

* [Issue #311](https://github.com/ansys/openapi-common/issues/311),
  [Pull request #312](https://github.com/ansys/openapi-common/pull/312):
  Support response type to status code mapping for response deserialization.

### Bugs fixed

* [Issue #313](https://github.com/ansys/openapi-common/issues/313),
  [Pull request #316](https://github.com/ansys/openapi-common/pull/316):
  Improve `ApiConnectionException` error message.

### Contributors

* Andy Grigg (Ansys)
* Ludovic Steinbach (Ansys)

## openapi-common 1.2.0, 2023-01-03

### New features

* [Issue #220](https://github.com/ansys/openapi-common/issues/220),
  [Pull request #221](https://github.com/ansys/openapi-common/pull/221):
  Handle `Enum` objects as properties of models.
* [Issue #129](https://github.com/ansys/openapi-common/issues/129),
  [Pull request #139](https://github.com/ansys/openapi-common/pull/139):
  Replace `requests-oauthlib` with `requests-auth`.

### Bugs fixed

* [Issue #284](https://github.com/ansys/openapi-common/issues/284),
  [Pull request #288](https://github.com/ansys/openapi-common/pull/288):
  Fix formatting path with multiple path parameters.

### Contributors

* Doug Addy (Ansys)
* Andy Grigg (Ansys)
* Ludovic Steinbach (Ansys)
* Kathy Pippert (Ansys)

## openapi-common 1.1.1, 2022-07-15

### New features

* [Issue #220](https://github.com/ansys/openapi-common/issues/220),
  [Pull request #221](https://github.com/ansys/openapi-common/pull/221):
  Handle `Enum` objects as properties of models.


### Contributors

* Doug Addy (Ansys)


## openapi-common 1.1.0, 2022-04-04

### Bugs fixed

* [Issue #170](https://github.com/ansys/openapi-common/issues/170),
  [Pull request #180](https://github.com/ansys/openapi-common/pull/180):
  Respect `response_type` when deserializing a JSON response.
* [Issue #171](https://github.com/ansys/openapi-common/issues/171),
  [Pull request #172](https://github.com/ansys/openapi-common/pull/172):
  Fix path parameter formatting in requests.
* [Issue #145](https://github.com/ansys/openapi-common/issues/145),
  [Pull request #146](https://github.com/ansys/openapi-common/pull/146):
  Fix error message for missing OIDC and kerberos extras.

### Documentation

* Standardize the syntax for different authentication types.

### Contributors

* Doug Addy (Ansys)
* Andy Grigg (Ansys)
* Ludovic Steinbach (Ansys)
* Kathy Pippert (Ansys)


## openapi-common 1.0.0, 2022-02-17

Initial release

### Contributors

* Doug Addy (Ansys)
* Andy Grigg (Ansys)
* Kathy Pippert (Ansys)
