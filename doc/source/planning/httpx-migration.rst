..
   Planning note: this page tracks the library migration from ``requests`` to ``httpx``.
   User-facing migration guides may be added later; see "Deferred" below.

HTTP client migration: ``requests`` → ``httpx``
=================================================

.. note::

   This document is an engineering plan and decision log for maintainers. It is not
   end-user documentation.

Goals
-----

* Replace ``requests`` with ``httpx`` for synchronous HTTP from OpenAPI-Common while
  preserving behavior that callers rely on (including retries on selected status codes,
  authentication flows, and session configuration).
* Ship the change as a **major** semantic-version release.
* Keep the door open for optional **HTTP/2** and **async** APIs later without designing
  the current spike around blocking assumptions.

Non-goals (this spike)
----------------------

* **Downstream OpenAPI generator templates** — deferred until the library implementation
  is stable; coordinate template updates in a follow-up.
* **Published user guide / migration guide updates** — deferred for this spike (README,
  user guide, Intersphinx links remain until a documentation pass).
* **HTTP/2** — not implemented now; avoid choices that would permanently prevent enabling
  ``http2`` on a future ``httpx`` client.
* **Async** — session creation and public API for this release remain **synchronous**
  (``httpx.Client``), aligned with current usage.

Agreed direction (decided so far)
---------------------------------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Topic
     - Decision
   * - Sync vs async
     - Stay **sync** for session and ``ApiClient`` transport for this major release.
   * - HTTP/2
     - **Do not implement** in the spike; do not hard-code decisions that forbid turning
       HTTP/2 on later.
   * - Versioning
     - **Major** release (breaking change for types and session objects).
   * - Configuration API
     - Introduce **``TransportConfiguration``** and **``get_transport_configuration()``**
       (or equivalent) for settings used to build the HTTP client—document that this is
       client/transport configuration, not necessarily a bare ``httpx.HTTPTransport``
       subclass unless we expose one explicitly.
   * - Retries
     - Preserve **400** in the set of status codes that trigger retry (intermittent
       server behavior).
   * - Retry implementation
     - Prefer a **subclass of ``httpx.HTTPTransport``** (analogous to the current
       ``HTTPAdapter`` + timeout wrapper). **Document in code** which **urllib3**
       ``Retry`` semantics are mirrored (status retries, backoff, connection vs read
       errors, etc.)—full parity with urllib3 is not assumed unless we implement it.
   * - Headers
     - Prefer **``httpx.Headers``** where it simplifies code. **``WWW-Authenticate``**
       remains parsed by **``parse_authenticate``**; use **``Headers.get_list("www-authenticate")``**
       (or equivalent) when multiple header field lines exist, then merge parsed schemes
       as needed for scheme selection.
   * - NTLM
     - Use an **httpx-native** NTLM auth path (e.g. **``httpx-ntlm``** / pyspnego-based),
       analogous to **``requests-ntlm``**, for password NTLM when required.
   * - Negotiate / Kerberos / SSPI
     - **Locked:** **Windows** — ``httpx-negotiate-sspi`` (``HttpSspiAuth`` from
       ``httpx_negotiate_sspi``), pinned for ``sys_platform == 'win32'``. **Linux** —
       ``httpx-gssapi`` (``HTTPSPNEGOAuth``) for integrated Negotiate on the ``httpx`` client.
       The ``[linux-kerberos]`` extra declares ``httpx-gssapi`` for Negotiate on Linux.
       Application code uses a single ``with_autologon()`` path;
       ``_session.py`` selects the backend by platform. Validation strategy:
       see negotiate-validation-strategy_.
   * - OIDC / OAuth2
     - Target **``httpx-auth``** for OAuth2/OIDC-style flows instead of **``requests_auth``**,
       pending a **spike** that proves parity for PKCE, client/session wiring, and edge
       cases (e.g. Auth0 ``audience`` / refresh behavior).
   * - Tests
     - Adopt **``pytest-httpx``** for HTTP mocking in place of **``requests-mock``** for
       the majority of tests. Legacy urllib3 / **``HTTPAdapter``**-oriented tests are
       rewritten against **``httpx``** responses or **``RetryingHTTPTransport``** behaviour
       (see implementation status below).

Implementation status (snapshot)
--------------------------------

This section tracks **what is already merged** versus **what remains** (cleanup).
Updated periodically while the migration branch evolves.

**Implemented in the current tree**

* **Configuration:** ``TransportConfiguration``, ``SessionConfiguration.get_transport_configuration()``,
  ``httpx_client_init_kwargs()``, and ``create_httpx_client_from_session_configuration()``.
* **Factory client:** ``ApiClientFactory`` constructs ``httpx.Client`` with
  ``RetryingHTTPTransport`` (default timeout from
  ``SessionConfiguration``, retries including **400**, exponential backoff on transport errors—see
  module docstring in ``_retry_transport.py``).
* **ApiClient:** Requires ``httpx.Client`` as ``rest_client`` (the factory path); legacy
  ``requests.Session`` support has been removed for this major release.
* **Case-insensitive mapping:** ``SessionConfiguration.headers`` and exception header snapshots use
  ``CaseInsensitiveDict``, **vendored** from Requests ``structures.py`` in
  ``_case_insensitive_dict.py`` (Apache-2.0 attributed in-file)—no dependency on ``requests`` for this type.

  **Why vendoring (not ``httpx.Headers``):** ``httpx.Headers`` is built for HTTP header semantics
  (combining, normalization); ``SessionConfiguration`` needs a general-purpose **mutable**
  case-insensitive **mapping** for arbitrary configuration keys. Vendoring preserves the same
  behaviour as the historical Requests type without pulling in ``requests`` at runtime.

* **WWW-Authenticate:** Multiple header field lines are gathered via ``httpx.Headers.get_list``;
  each challenge string is passed to ``parse_authenticate`` and merged for scheme detection
  (``_session.py``).
* **Credential auth:** Basic, NTLM (``httpx-ntlm``, Windows), Negotiate / SSPI (``httpx-negotiate-sspi``),
  Linux Negotiate (``httpx-gssapi``) on the shared ``httpx`` client.
* **OIDC:** ``OIDCSessionFactory`` builds **``httpx.Client``** instances (API + IdP) via
  ``create_httpx_client_from_session_configuration``. OAuth uses **``httpx-auth``**
  ``OAuth2AuthorizationCodePKCE`` with ``client=`` (shared IdP client). ``WWW-Authenticate``
  for Bearer challenges uses the same multi-line header collection as the factory path
  (``collect_www_authenticate_raw_values``). Builder API (**``OIDCSessionBuilder``**) unchanged.
* **Tests:** Session flows largely mock HTTP with ``pytest-httpx``. Timeout and retry wiring are
  covered by ``tests/test_session_configuration.py::TestHttpxClientTransportFromSessionConfiguration``
  and ``tests/test_retry_transport.py``. The old **``_RequestsTimeoutAdapter``** helper has been
  removed.

**Still outstanding**

* **OIDC hardening:** Confirm **``httpx-auth``** PKCE flows match production expectations end-to-end
  (Auth0 ``audience``, refresh rotation, interactive browser timeout)—parity was preserved in unit tests,
  not a full IdP matrix.
* **Phase 6 (tests):** ``requests-mock`` removed from dev dependencies; ``pytest-httpx`` is used for HTTP
  mocking (including ``tests/test_api_client.py``).
* **Phase 7 (dependencies):** Runtime ``requests`` / legacy ``requests-*`` packages and ``types-requests``
  removed from ``pyproject.toml`` (library and tests use ``httpx`` only).

Technical outline
-----------------

#. **Dependencies**

   * Runtime: ``httpx``; remove or narrow ``requests`` once migration is complete.
   * Typing: rely on ``httpx``'s inline types; drop ``types-requests`` when unused.
   * Optional auth: replace ``requests-*`` extras with httpx-oriented packages per
     platform and flow (NTLM, Negotiate/SSPI, Kerberos/GSSAPI, OIDC).

#. **Client construction**

   * Replace ``requests.Session()`` with ``httpx.Client(...)`` built from
     ``TransportConfiguration`` / ``get_transport_configuration()`` instead of mutating
     session ``__dict__`` (``set_session_kwargs`` pattern).

#. **Retries and timeouts**

   * Implement retry + default timeout in the **custom ``HTTPTransport``** subclass,
     matching agreed urllib-inspired semantics and preserving **400** in the retryable
     status set.

#. **API surface**

   * ``ApiClient`` and factories accept an **httpx client** (and types/docs updated for
     ``httpx.Response`` where applicable, e.g. ``reason_phrase`` vs ``reason``).

#. **WWW-Authenticate**

   * Keep **``parse_authenticate``**; call sites merge **one parsed dict per header field line**
     (``httpx.Headers.get_list("www-authenticate")``). Implemented in ``_session.py``.

#. **Testing**

   * **``pytest-httpx``** for URL-level mocking; custom POST/body checks use callbacks or
     captured request assertions.
   * **``test_api_client.py``** uses **synthetic ``httpx.Response``** helpers (no ``requests`` or
     urllib3 response fixtures).
   * **Done:** former **timeout adapter** tests are replaced by factory **``httpx.Client``**
     assertions plus ``tests/test_retry_transport.py``.

Implementation order (phased)
-----------------------------

This section is the suggested **sequence of work** so each stage stays testable in CI
before layering complexity. **Authentication is deliberately narrowed first**: Basic
(and anonymous) flows use only ``httpx``'s built-in auth and simple header logic, so the
HTTP stack, response model, and configuration plumbing can be validated **before** NTLM,
Negotiate/Kerberos, SSPI, or OIDC packages are introduced.

Why Basic first
~~~~~~~~~~~~~~~

* **Fewer moving parts**: ``httpx.BasicAuth`` maps directly from today’s password
  flows when the server advertises **Basic** or the caller forces **Basic**.
* **Same ``WWW-Authenticate`` parsing**: ``parse_authenticate`` already produces scheme
  keys; Basic-only branch exercises **``httpx`` responses + headers** without pyspnego,
  SSPI, or OAuth libraries.
* **Early CI signal**: Core ``ApiClient`` / serialization / exception paths run green
  while heavier auth is still ported.

Phases (do roughly in this order)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each phase should end with **tests passing** (full suite or an agreed subset marked
with ``pytest`` markers until later phases land).

.. list-table::
   :header-rows: 1
   :widths: 8 42 50

   * - Step
     - Scope
     - How to verify
   * - **1**
     - **Dependencies + configuration API.** Add ``httpx``. Introduce
       ``TransportConfiguration`` and ``get_transport_configuration()`` (and retire
       ``RequestsConfiguration`` / ``get_configuration_for_requests()`` as part of the
       major bump). Replace ``set_session_kwargs`` with **explicit**
       ``httpx.Client(...)`` construction from that mapping.
     - Unit tests only: configuration round-trip, no live HTTP. Types and public names
       compile.
   * - **2**
     - **Anonymous HTTP + Basic credentials only.** Wire ``ApiClient`` to use
       ``httpx`` verb helpers; switch exceptions and deserialization to
       ``httpx.Response`` (``reason_phrase``, headers). **In the current branch** the factory
       client already uses **``RetryingHTTPTransport``** (step 3) rather than a bare default
       transport—steps 2 and 3 are combined for production code. Implement **Basic** auth first:
       ``AuthenticationScheme.BASIC``, and **AUTO** only when
       ``parse_authenticate`` yields **Basic** (other schemes: document as “not yet
       available” or skip with a clear error until step 5).
     - ``pytest`` on anonymous + Basic-only paths; **``pytest-httpx``** (or synthetic
       ``httpx.Response`` builders) for ``ApiClient`` behavior. Replace urllib3-based
       **response fixtures** in tests as soon as this step touches them.
   * - **3**
     - **Custom ``HTTPTransport``** (timeout defaults, retries incl. **400**, backoff).
       Document urllib3 **Retry** semantics you mirror in a file/class comment (**implemented**
       in ``_retry_transport.py``).
     - Dedicated transport unit tests (**``tests/test_retry_transport.py``**) and
       **``TestHttpxClientTransportFromSessionConfiguration``** (session configuration module)
       replacing legacy urllib3 ``HTTPAdapter`` timeout patching.
   * - **4**
     - **NTLM** (e.g. ``httpx-ntlm``) and **Negotiate / Kerberos / SSPI** using chosen
       platform packages. Expand ``with_credentials`` **AUTO** for real servers.
     - Existing session-creation tests ported to ``httpx`` + optional extras; manual or
       integration tests against representative hosts if available.
   * - **5**
     - **OIDC / OAuth2** via ``httpx-auth`` (or confirmed alternative), rewriting
       ``_oidc.py`` and optional extras.
     - OIDC unit/integration tests; spike checklist closed (PKCE, refresh, Auth0 edge
       cases).
   * - **6**
     - **Test suite consolidation.** Migrate remaining **``requests-mock``** usage to
       **``pytest-httpx``**; align POST body matchers; drop **``requests``**-only dev
       deps when unused.
     - Full ``pytest`` green; coverage comparable to pre-migration baseline.
   * - **7**
     - **Dependency cleanup.** Remove ``requests``, ``types-requests``, and obsolete
       ``requests-*`` packages from runtime where replaced; refresh ``pyproject.toml`` /
       lockfile.
     - Clean install + CI; no stray imports.

What to do first (short answer)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. **Configuration + ``httpx.Client`` skeleton** (steps 1–2): types and anonymous requests,
   then Basic auth on ``ApiClient`` / factory paths.
#. **Retry transport** (step 3): restore production resilience before SSO debugging.
#. **NTLM / Negotiate / OIDC** (steps 4–5): unlock full **AUTO** and enterprise flows.
#. **Tests + dependency purge** (steps 6–7).

Parallelism
~~~~~~~~~~~

* **Docs** (user-facing migration guide) and **generator templates** remain deferred;
  this planning page can still be updated as decisions land.
* **pytest-httpx** adoption can start in **step 2** for new/changed tests; a full sweep
  fits **step 6**.
* **Step 3 before steps 4–5 is recommended** so retry behavior is stable before debugging
  SSO stacks.

Expected test suite status by phase
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use this as a **checkpoint list** when running ``uv run pytest``. Exact counts drift as
tests are added; the authoritative inventory is ``uv run pytest --collect-only -q``.

.. note::

   Baseline (current tree): **355** tests collected. Some tests are **skipped** today
   (e.g. ``test_invalid_header_malformed`` in ``test_parse_authenticate.py``). **NTLM**
   session tests use ``skipif`` (non-Windows or missing ``httpx_ntlm``), not blanket skips.
   ``tests/integration/test_negotiate.py`` is marked ``kerberos`` and only runs with ``--with-kerberos``.

Phase 1 — configuration API only
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Goal:** Green suite for modules that do **not** open HTTP connections and do **not**
depend on ``requests.Session`` / adapters.

.. list-table::
   :header-rows: 1
   :widths: 38 62

   * - Scope (expect pass)
     - Notes
   * - ``tests/test_parse_authenticate.py``
     - Parser unit tests only (no HTTP stack).
   * - ``tests/test_utils_misc.py``
     - ``CaseInsensitiveOrderedDict``.
   * - ``tests/test_unset.py``
     - Single test.
   * - ``tests/test_model_methods.py``
     - Model serialization helpers.
   * - ``tests/test_session_configuration.py`` (partial)
     - **Include:** ``test_defaults`` through ``test_redirects``, all of
       ``TestDeserialization`` **except** ``test_assign_all_values``. **Exclude:**
       ``test_cookies`` (uses ``httpx.Client.build_request`` to assert serialized cookies). Timeout/retry
       tests that once targeted ``HTTPAdapter`` now live under Phase 3 class names (see below).

**Rough count:** ~55–60 tests (four full modules + partial ``test_session_configuration``).

Phase 2 — ApiClient + anonymous + Basic
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Goal:** Everything that exercises **``httpx.Client``**, **``ApiClient``**, **Basic**
auth, and **anonymous** flows, without requiring NTLM, Negotiate, or OIDC. (The factory
client includes **``RetryingHTTPTransport``**; retry behaviour is validated under Phase 3
tests.)

.. list-table::
   :header-rows: 1
   :widths: 38 62

   * - Scope (expect pass)
     - Notes
   * - ``tests/test_exceptions.py``
     - Switch mocks to ``httpx`` responses.
   * - ``tests/test_api_client.py``
     - Full file (fixtures move from ``requests.Session`` to ``httpx.Client``;
       ``TestResponseParsing`` uses synthetic ``httpx.Response`` instead of urllib3).
   * - ``tests/integration/test_anonymous.py``
     - Live FastAPI harness.
   * - ``tests/integration/test_basic.py``
     - Basic-auth integration (AUTO + BASIC modes against real server).
   * - ``tests/test_session_configuration.py`` (remainder from Phase 1)
     - ``test_cookies``; ``TestDeserialization::test_assign_all_values``.
   * - ``tests/test_session_creation.py`` (subset)
     - **Expect pass:** ``test_anonymous``; ``test_other_status_codes_throw``;
       ``test_missing_www_authenticate_throws``; ``test_unconfigured_builder_throws``;
       ``test_can_connect_with_basic`` and the three related Basic variants;
       ``test_only_called_once_with_basic_when_anonymous_is_ok`` for
       ``AuthenticationScheme.AUTO`` and ``.BASIC`` only;
       ``test_throws_with_invalid_credentials`` (**AUTO** / **BASIC** always; **NTLM**
       Windows-only with ``httpx_ntlm`` / pyspnego — see Phase 4);
       ``test_with_credentials_throws_with_invalid_auth_method``;
       ``test_self_signed_throws``; ``test_invalid_initial_response_raises_exception``.
   * - Still **not** Phase 2
     - Any test whose name implies **NTLM**, **Negotiate**, **autologon**, or **OIDC**;
       parametrized cases **NTLM** on Basic flows; ``test_neither_basic_nor_ntlm_throws``;
       ``test_no_autologon_throws``; ``test_no_oidc_throws``.

Phase 3 — custom ``HTTPTransport`` (timeouts + retries)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Goal:** Document and test **``RetryingHTTPTransport``** (timeouts from ``SessionConfiguration``,
retries, backoff). Legacy ``_RequestsTimeoutAdapter`` is **removed**.

.. list-table::
   :header-rows: 1
   :widths: 38 62

   * - Scope (expect pass)
     - Notes
   * - ``tests/test_retry_transport.py``
     - Status retries, transport-error retries, max attempts, disallowed methods.
   * - ``tests/test_session_configuration.py::TestHttpxClientTransportFromSessionConfiguration``
     - Client default/custom timeout and ``retry_count`` → transport ``max_attempts``.
   * - ``tests/test_session_configuration.py::TestWwwAuthenticateHeaderMerging``
     - Multiple ``WWW-Authenticate`` header lines merged for scheme detection.

Phase 4 — NTLM + Negotiate / Kerberos / SSPI
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Goal:** Complete credential flows beyond Basic.

.. list-table::
   :header-rows: 1
   :widths: 38 62

   * - Scope (expect pass)
     - Notes
   * - ``tests/test_session_creation.py`` (remaining auth)
     - NTLM handshake tests (**``test_can_connect_with_ntlm``**, **``test_throws_with_invalid_credentials``**
       for **NTLM**); Negotiate / autologon paths; parametrized **NTLM** cases on shared Basic
       tests; ``test_neither_basic_nor_ntlm_throws``; ``test_no_autologon_throws``.
   * - ``tests/integration/test_negotiate.py``
     - Runs only with ``--with-kerberos`` (Linux-oriented).
   * - ``tests/test_missing_imports.py::test_create_autologon_on_linux_with_no_extra_throws``
     - Linux only; update **blocked import** name if Kerberos extra package changes.

.. _negotiate-validation-strategy:

Negotiate validation strategy (locked packages)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Packages are declared in ``pyproject.toml`` (base deps on Windows; ``[linux-kerberos]``
on Linux). **Automated CI** does **not** reproduce a domain-attached Windows SSPI client
or a full internal KDC for ``httpx`` Negotiate—those environments are costly and
environment-specific.

* **Linux:** Optional integration coverage via ``tests/integration/test_negotiate.py``,
  run only with ``pytest --with-kerberos`` when a Kerberos test harness (e.g. ``asgi_gssapi``
  + KDC) is available—see ``pytest.mark.kerberos`` in ``tests/conftest.py``.

* **Windows (SSPI):** No portable Negotiate integration test in public CI. Periodically
  validate **manually** against an **internal or staging HTTP API** that returns
  ``401`` with ``WWW-Authenticate: Negotiate``—for example call
  ``ApiClientFactory(api_url).with_autologon().connect()`` (and an authenticated request)
  from a domain-joined or suitably configured workstation. Record regressions if behaviour
  diverges after dependency bumps (``httpx-negotiate-sspi``, ``httpx``, etc.).

Phase 5 — OIDC / OAuth2
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 38 62

   * - Scope (expect pass)
     - Notes
   * - ``tests/test_oidc.py``
     - Entire file (currently ``requests`` / ``requests_auth`` oriented).
   * - ``tests/test_session_creation.py`` (OIDC tests)
     - ``test_can_connect_with_oidc`` and related ``with_oidc`` / token variants;
       ``test_only_called_once_with_oidc_when_anonymous_is_ok``;
       ``test_no_oidc_throws``.
   * - ``tests/test_missing_imports.py::test_create_oidc_with_no_extra_throws``
     - Adjust **extra** / import name when OIDC dependency changes.

Phases 6–7 — test tooling + dependency purge
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Goal:** Full **355**-test (or successor) suite under ``uv run pytest`` with
**``pytest-httpx``**, no **``requests-mock``** where migrated, and runtime **without**
``requests``. Treat prior phases as included; CI should match **pre-migration**
coverage expectations.

Suggested pytest shortcuts (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use **deselect** / node IDs until later phases land, e.g. exclude OIDC module entirely:

.. code-block:: shell

   uv run pytest tests/ --ignore=tests/test_oidc.py

(or narrow paths explicitly). Prefer **documented markers** if you introduce
``@pytest.mark.httpx_phaseN`` during the spike.

Deferred (explicit)
-------------------

* **Downstream OpenAPI templates** — update generated clients after this library stabilizes.
* **End-user documentation** — migration notes, user guide, Intersphinx, README refresh.

Outstanding decisions / follow-ups
------------------------------------

These remain open or need validation work. Items marked **locked** are decided; follow bullets
are maintenance and validation notes, not open package selection.

#. **OIDC spike**

   * Confirm **``httpx-auth``** exposes flows equivalent to **``OAuth2AuthorizationCodePKCE``**
     (session/client injection, PKCE, token refresh, **``InvalidGrantRequest``**-style
     errors, Auth0 ``audience`` workaround).

#. **Negotiate / Kerberos (locked; maintenance)**

   * **Linux:** ``httpx-gssapi`` for Negotiate in ``with_autologon()``; the ``[linux-kerberos]``
     extra installs ``httpx-gssapi``.
     Integration tests are optional (``--with-kerberos``); CI alignment is **not** required
     for every PR unless that job is enabled.

   * **Windows:** ``httpx-negotiate-sspi`` (SSPI). **CI does not** exercise live Negotiate;
     validate against an **internal server** or staging API as described in
     negotiate-validation-strategy_.

   * **Ongoing:** Keep pins compatible with ``python-gssapi`` / OS krb5 on supported Linux
     distros; bump ``httpx-negotiate-sspi`` as needed after smoke tests on Windows.

#. **Retry semantics** (**resolved in code**)

   * **``RetryingHTTPTransport``** retries selected **HTTP statuses** (including **400**) for
     configured methods, and retries **transport-level failures** (timeouts, ``NetworkError``,
     ``ProxyError``, ``RemoteProtocolError``) with exponential backoff—see the class/module
     docstring in ``_retry_transport.py``. This is **not** full urllib3 ``Retry`` parity.

#. **Idempotency / POST + retries** (**documented in transport**)

   * POST (and other methods) may be retried on retryable statuses; the transport docstring
     notes the duplicate side-effect risk. Promote to user-facing guidance only if product
     communications require it.

#. **``SessionConfiguration.headers`` type** (**resolved**)

   * **``CaseInsensitiveDict``** is **vendored** (Requests-derived implementation in
     ``_case_insensitive_dict.py``), exported from the package public API. Using **``httpx.Headers``**
     for arbitrary configuration keys was rejected as semantically wrong.

#. **POST body matching in tests** (**done for ``test_api_client.py``**)

   * **``requests-mock``** ``additional_matcher`` patterns were ported to **``pytest-httpx``**
     callbacks / assertions on captured requests.

References
----------

* `httpx documentation <https://www.python-httpx.org/>`_
* `pytest-httpx <https://pypi.org/project/pytest-httpx/>`_
