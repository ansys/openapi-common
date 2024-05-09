# Changelog

This project uses [towncrier](https://towncrier.readthedocs.io/) and the
changes for the upcoming release can be found in
<https://github.com/ansys/openapi-common/tree/main/doc/changelog.d/>.

<!-- towncrier release notes start -->

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
