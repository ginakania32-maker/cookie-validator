"""
Cookie Validator - Architecture & Flow Documentation

## System Architecture

### High-Level Flow
```
User Interaction
    ↓
GUI Folder Picker (tkinter)
    ↓
Folder Scanner (Recursive)
    ↓
File Detection (cookies.txt, *.txt, *.json)
    ↓
Advanced Validator Orchestrator
    ↓
Worker Pool (Semaphore-based)
    ├─ Worker 1  ├─ Worker 5  ├─ Worker 9
    ├─ Worker 2  ├─ Worker 6  ├─ Worker 10
    ├─ Worker 3  ├─ Worker 7
    ├─ Worker 4  ├─ Worker 8
    ↓
Per-File Validation Pipeline
    ├─ Cookie Format Detection
    ├─ Cookie Parsing
    ├─ Cookie Normalization
    ├─ CookieJar Building
    └─ Endpoint Testing (Sequential)
        ├─ Test /v2/account
        ├─ Test /v2/auth/verify
        ├─ Test /api/v2/account
        ├─ Test /account/settings
        └─ (etc)
    ↓
Status Determination
    ├─ HTTP Status Analysis
    ├─ Content Pattern Matching
    ├─ Email Extraction
    └─ Email Confirmation
    ↓
Result Persistence
    ├─ Status-specific files (valid.txt, invalid.txt, etc)
    ├─ JSON results file
    ├─ Debug responses (if enabled)
    └─ Summary statistics
    ↓
Output & Reporting
    ├─ Colored terminal output
    ├─ Real-time progress
    └─ Summary statistics
```

### Async Task Distribution
```
Event Loop
    ↓
Advanced Validator (Async Orchestrator)
    ├─ File Scanner (1 task)
    ├─ Validation Queue (async.Queue)
    ├─ Worker Manager
    │   ├─ Worker 1-N (async coroutines)
    │   │   ├─ Acquire Semaphore
    │   │   ├─ Get task from queue
    │   │   ├─ Validate cookie
    │   │   │   ├─ Build CookieJar
    │   │   │   ├─ Test endpoints
    │   │   │   └─ Determine status
    │   │   ├─ Write result
    │   │   ├─ Release Semaphore
    │   │   └─ Next task
    └─ Result Writer (async)
        ├─ Write to status files
        └─ Write JSON results
```

### Cookie Validation Pipeline
```
Input: Cookie File (cookies.txt or *.json)
    ↓
[1] Format Detection
    ├─ Content starts with {  or [ → JSON
    ├─ Content starts with #   → Netscape
    ├─ Contains \t and TRUE    → Netscape
    └─ Default → Netscape
    ↓
[2] Parsing
    ├─ JSON Parser
    │   ├─ Array format → Extract each cookie
    │   ├─ Object format → Handle nested
    │   └─ Normalize fields
    ├─ Netscape Parser
    │   ├─ Split by tabs
    │   ├─ Extract: domain, path, name, value, expiry
    │   └─ Normalize fields
    ↓
[3] Normalization
    ├─ Standard cookie dict format
    ├─ Default values for missing fields
    └─ Domain normalization
    ↓
[4] CookieJar Building
    ├─ httpx.CookieJar()
    ├─ Set each cookie with attributes
    └─ Return jar with all cookies
    ↓
[5] Endpoint Testing (Priority Order)
    ├─ Prepare headers with UA rotation
    ├─ Prepare proxies with rotation
    ├─ For each endpoint:
    │   ├─ GET request with CookieJar
    │   ├─ Handle timeouts/errors with retry
    │   ├─ Exponential backoff on failure
    │   └─ Return response
    ↓
[6] Status Detection
    ├─ Check HTTP status code
    │   ├─ 401 → INVALID
    │   ├─ 403 → FORBIDDEN
    │   ├─ 429 → RATE_LIMIT
    │   └─ 200 → Continue analysis
    ├─ Check for captcha patterns → CAPTCHA
    ├─ Check redirect URL
    │   └─ Redirect to /login → EXPIRED
    ├─ Check response content
    │   ├─ "Sign In" + non-200 → EXPIRED
    │   ├─ Authenticated indicators → VALID
    │   └─ "Unauthorized" → INVALID
    ├─ Extract email if authenticated
    └─ Return: (Status, Details)
    ↓
Output: ValidationResult
    ├─ filename
    ├─ status (VALID|INVALID|EXPIRED|...)
    ├─ endpoint_tested
    ├─ status_code
    ├─ email (if VALID)
    ├─ error_message
    └─ metadata (timestamps, sizes, etc)
```

### HTTP Request Flow
```
CookieValidator.validate()
    ↓
HttpClientFactory.request_with_retry()
    ↓
For attempt in range(max_retries):
    ├─ Create AsyncClient
    │   ├─ Headers (with UA rotation)
    │   ├─ CookieJar (from file)
    │   ├─ Proxy (with rotation if enabled)
    │   ├─ Timeout config
    │   └─ Connection limits
    │
    ├─ Make GET request
    │   ├─ Follow redirects (config)
    │   ├─ Handle response
    │   └─ Return response
    │
    ├─ Success → Return response
    │
    ├─ Timeout/Error → Calculate delay
    │   ├─ delay = base * (backoff_factor ^ attempt)
    │   ├─ delay = min(delay, max_delay)
    │   ├─ Sleep for delay
    │   └─ Retry
    │
    └─ Final attempt fails → Return None
```

### Worker Pool Coordination
```
Main Event Loop
    ↓
Advanced Validator.validate_batch()
    ├─ Create asyncio.Queue()
    ├─ Add N tasks to queue
    ├─ Create N workers (coroutines)
    │
    ├─ Each worker:
    │   ├─ While not done:
    │   │   ├─ Try acquire semaphore (max_workers concurrent)
    │   │   ├─ Get task from queue
    │   │   ├─ Validate cookie
    │   │   ├─ Write result
    │   │   ├─ Release semaphore
    │   │   └─ Mark task done
    │   │
    │   └─ Workers wait for tasks via asyncio.gather()
    │
    └─ Main waits for all workers via asyncio.gather()
        ├─ All workers complete or error occurs
        ├─ Write final JSON
        ├─ Print summary
        └─ Return results

Concurrency Control:
    - Semaphore(max_workers=10)
    - Max 10 concurrent HTTP requests
    - Remaining tasks wait in queue
    - No busy-waiting (async sleep)
```

### File Output Structure
```
results/
├── valid.txt
│   └─ Newline-separated valid filenames
├── invalid.txt
│   └─ Newline-separated invalid filenames
├── expired.txt
│   └─ Newline-separated expired filenames
├── forbidden.txt
│   └─ Newline-separated 403 filenames
├── ratelimit.txt
│   └─ Newline-separated rate-limited filenames
├── results.json
│   ├─ timestamp
│   ├─ total (count)
│   ├─ summary
│   │   ├─ valid (count)
│   │   ├─ invalid (count)
│   │   ├─ expired (count)
│   │   ├─ forbidden (count)
│   │   └─ rate_limit (count)
│   └─ results[]
│       └─ Each ValidationResult as JSON
└── debug/
    ├─ cookie1_/v2/account_response.txt
    ├─ cookie2_/v2/projects_response.txt
    └─ (Failed response bodies for analysis)
```

### Configuration Propagation
```
config.py (Pydantic BaseSettings)
    ├─ Read from environment variables
    ├─ Read from .env file
    ├─ Use defaults
    └─ Validate with Pydantic

config instance (singleton)
    ├─ main.py → Uses global config
    ├─ validator.py → Uses global config
    ├─ advanced_validator.py → Uses global config
    ├─ helpers/http_client.py → Uses global config
    ├─ helpers/cookie_helpers.py → Uses global config
    └─ helpers/logger.py → Uses global config

Benefits:
    - Single source of truth
    - Environment variable override
    - Type-safe configuration
    - No hardcoded values
```

### Error Handling Flow
```
Cookie Validation
    ├─ File Read Error
    │   ├─ Log error
    │   ├─ Return ERROR status
    │   └─ Continue to next file
    │
    ├─ Parse Error
    │   ├─ Log warning
    │   ├─ Skip invalid lines
    │   ├─ Continue parsing
    │   └─ Return parsed cookies
    │
    ├─ HTTP Error
    │   ├─ Timeout → Retry with backoff
    │   ├─ Connection refused → Retry
    │   ├─ SSL error → Return response
    │   └─ Max retries → Return None/ERROR
    │
    ├─ Status Detection Error
    │   ├─ Fallback to INVALID
    │   ├─ Log error
    │   └─ Continue
    │
    └─ Worker Error
        ├─ Catch exception
        ├─ Log error
        ├─ Mark task done
        └─ Continue to next task
```

### Data Flow Through Modules
```
Input Cookie File
    ↓ (FileScanner)
Path object
    ↓ (CookieValidator)
Normalized cookies dict
    ↓ (CookieJarBuilder)
httpx.CookieJar
    ↓ (HttpClientFactory)
httpx.Response
    ↓ (AuthenticationDetector)
(Status, Details) tuple
    ↓ (CookieValidator)
ValidationResult dataclass
    ↓ (ValidationWriter)
Files & JSON output
    ↓ (Logger)
Terminal output
```

## Class Relationships

### Config Layer
```
config.py
├─ ValidatorConfig (Pydantic)
│   └─ Global instance: config
├─ ValidationStatus (Enum)
├─ CookieFormat (Enum)
└─ Constants (COLORS, USER_AGENTS, etc)
```

### Helpers Layer
```
helpers/
├─ logger.py
│   ├─ ColoredFormatter
│   ├─ ValidatorLogger
│   └─ Global: logger
│
├─ http_client.py
│   ├─ RetryConfig (dataclass)
│   ├─ UserAgentRotator
│   ├─ ProxyRotator
│   ├─ HeaderBuilder
│   ├─ HttpClientFactory
│   └─ Global: http_client_factory
│
└─ cookie_helpers.py
    ├─ CookieNormalizer
    ├─ CookieJarBuilder
    ├─ AuthenticationDetector
    ├─ EndpointDiscoverer
    └─ FileScanner
```

### Core Layer
```
validator.py
├─ ValidationResult (dataclass)
├─ CookieValidator
└─ ValidationWriter

advanced_validator.py
├─ WorkerStats (dataclass)
├─ ValidationQueue
├─ WorkerPool
└─ AdvancedValidator
```

### Interface Layer
```
main.py
├─ FolderPickerGUI
├─ ValidatorCLI
└─ main() entry point
```

## Performance Characteristics

### Time Complexity
- N = number of cookies
- M = number of endpoints tested per cookie
- W = number of workers
- R = max retries

Per-worker: O(N/W * M * R)
Total with workers: O(N/W * M * R)
Concurrent speedup: ~W times faster than sequential

### Space Complexity
- O(N) for storing results
- O(M) for endpoints list
- O(W) for worker pool
- O(C) for cookies in memory (C = avg cookies per file)

### Optimization Points
1. Worker pool size: Balance CPU usage vs queue wait time
2. Timeout values: Too short = retries, too long = slow failures
3. Retry backoff: Too aggressive = miss valid attempts, too conservative = slow
4. Endpoint count: More endpoints = higher accuracy but slower

## Security Considerations

### Cookie Handling
- Cookies never logged (except debug mode)
- Cookies only transmitted to target URL
- Support for proxy authentication
- No cookie persistence beyond session

### HTTP Security
- HTTPS by default (cloud.digitalocean.com)
- SSL verification enabled
- Realistic headers prevent detection
- Proxy support for anonymization

### File Security
- Debug files only contain response headers/body
- No sensitive data in logs (except debug mode)
- Results stored locally only
- Support for environment variables (no hardcoded secrets)

## Monitoring & Debugging

### Logging Levels
- DEBUG: Detailed request/response info
- INFO: Validation progress and results
- WARNING: Retries and non-fatal issues
- ERROR: Failures and exceptions

### Debug Mode
Enable in config.py:
```python
DEBUG = True
DEBUG_SAVE_RESPONSES = True
```

Saves responses to: results/debug/

### Performance Metrics
- Printed after each run
- Total time, average per file
- Status breakdown with percentages
- Worker stats (if available)
"""

__doc__ = __doc__
