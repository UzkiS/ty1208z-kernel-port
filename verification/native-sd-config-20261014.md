# Native OpenWrt noninteractive SD-audit configuration

The clean native core run 38428158682 and both application jobs in
38428158727 failed in Linux syncconfig. The new HI3798MV100_SD_AUDIT option
was absent from the common target fragment; Linux asked a new question with
no interactive input. Existing locally resolved configurations concealed it.

The common fragment now explicitly disables this independent diagnostic.
No SD driver is enabled in the ordinary native router by this change.

Actual OpenWrt `.config.set` inputs from core, Ethernet, plain applications,
router, container compilation and native Wi-Fi were tested against the real
patched Linux Kconfig in fresh output directories. Removing the explicit
setting reproduces the new SD-audit option in every non-block profile.
Adding the shared setting removes it; all six fixed inputs report no new
options via listnewconfig. The container build cannot reach this option because
BLOCK is enabled. This is local configuration validation; a later clean
Actions result is still required to establish remote build acceptance.
