# GC UI synthetic preview — navigation and screen-reader focus

This first-party static preview remains **fictional and disconnected**. This narrow improvement makes client-side view changes focus the visible view's heading, updates the main landmark's aria-labelledby relationship, and places live result counts on the small device-count status rather than re-announcing an entire dynamic list of fictional devices.

The source-only Node checks require all four section headings to be programmatically focusable and the count status to be atomic. The existing branch-scoped hosted Chromium interaction smoke exercises both desktop and mobile navigation focus, page heading/landmark identity and theme/filter behavior, with no accounts, Wi-Fi, Bluetooth, household device control or production Home Assistant backend.

This does **not** amount to a human screen-reader certification, real-device accessibility review, RTL/400% reflow acceptance, or the actual GC UI-branded Home Assistant frontend release. These remain open in [release issue #1](https://github.com/GoreeCloud/home-manager/issues/1).

## Narrow RTL browser reflow smoke (review only)

The explicit development-only URL query gc-preview-test=1&gc-preview-layout=rtl checks the actual Chromium CSS viewport, hidden desktop sidebar, visible mobile dock, heading focus and updated aria-current for every fictional view, plus visible-heading bounds and the absence of document-level horizontal overflow in a narrow right-to-left sample. GitHub Actions runs this smoke in a disposable 390×844 headless browser only for the first-party PR. It does **not** prove translated Arabic/Hebrew copy, direction-aware icons, full mobile or screen-reader accessibility, every screen size, or 200–400% text zoom. Real-device and assistive-technology acceptance remain open.
