/* SPDX-License-Identifier: ISC */
int wland_start_chip(struct net_device *ndev)
{
	struct wland_if *ifp;
	struct wland_private *drvr;
	u32 memory_address = 0;
	u8 chip_version = 0;
	char firmware_version[21] = {};
	int err;
#ifdef WLAND_FIRMWARE_PATH_FILE
	char firmware_path[5] = {};
#endif

	if (!ndev)
		return -ENODEV;
	ifp = netdev_priv(ndev);
	if (!ifp || !ifp->drvr || !ifp->drvr->bus_if)
		return -ENODEV;
	drvr = ifp->drvr;

	/* Existing ready state is trusted; this is not a liveness probe. */
	if (drvr->bus_if->chip_ready)
		return 0;

#ifdef WLAND_FIRMWARE_PATH_FILE
#ifdef WLAND_DRIVER_RELOAD_FW
	if (first_download_fw) {
#endif
		err = wland_nvram_read(WLAND_FIRMWARE_PATH_FILE,
				      firmware_path, sizeof(firmware_path) - 1, 0);
		if (err > 0 && err < sizeof(firmware_path)) {
			firmware_path[err] = '\0';
			if (!strcmp(firmware_path, "sta") ||
			    !strcmp(firmware_path, "ap"))
				strcpy(rdawlan_firmware_path, firmware_path);
		}
#ifdef WLAND_DRIVER_RELOAD_FW
	}
#endif
#endif
	if (strcmp(rdawlan_firmware_path, "sta") &&
	    strcmp(rdawlan_firmware_path, "ap") &&
	    strcmp(rdawlan_firmware_path, "p2p"))
		return -EPERM;

	err = wland_bus_active(drvr->bus_if);
	if (err < 0)
		goto fail;

	if (drvr->bus_if->chip == WLAND_VER_91_H) {
#ifdef WLAND_SDIO_SUPPORT
		struct wland_sdio_dev *sdiodev = drvr->bus_if->bus_priv.sdio;
		struct wland_sdio *bus = sdiodev->bus;

		bus->intr = true;
		bus->poll = false;
#ifdef WLAND_RDAPLATFORM_SUPPORT
		rda_mmc_set_sdio_irq(1, true);
#endif
#endif
		err = wland_fil_get_cmd_data(ifp, WID_MEMORY_ADDRESS,
					     &memory_address, sizeof(memory_address));
		if (err < 0)
			goto fail;
		/* A status-only acknowledgement is not firmware-state data. */
		if (err != sizeof(memory_address)) {
			err = -EPROTO;
			goto fail;
		}
		if (memory_address != 0xffffffff) {
			err = wland_download_codefile(ifp);
			if (err < 0)
				goto fail;
			err = wland_download_datafile(ifp);
			if (err < 0)
				goto fail;
			err = wland_run_firmware(ifp, RDA5991H_CODE_ADDR);
			if (err < 0)
				goto fail;
		}
#ifdef WLAND_MACADDR_EFUSE
		if (drvr->bus_if->up_data_mac) {
			err = wland_cfg80211_updata_mac(drvr->config);
			if (err < 0)
				WLAND_ERR("update mac addr failed: %d\n", err);
		}
#endif
		if (strcmp(rdawlan_firmware_path, "ap")) {
			/* The first firmware write must remain the preinit WIDs. */
			err = wland_preinit_cmds_91h(ifp);
			if (err < 0)
				goto fail;
			err = wland_set_scan_timeout(ifp);
			if (err < 0)
				goto fail;
		}
	}

	/* WID_CHIP_VERSION is a revision byte, not a measured chip family. */
	err = wland_fil_get_cmd_data(ifp, WID_CHIP_VERSION,
				     &chip_version, sizeof(chip_version));
	if (err < 0)
		goto fail;
	if (err != sizeof(chip_version)) {
		err = -EPROTO;
		goto fail;
	}
	err = wland_fil_get_cmd_data(ifp, WID_FIRMWARE_VERSION,
				     firmware_version, sizeof(firmware_version) - 1);
	if (err < 0)
		goto fail;
	if (!err || err >= sizeof(firmware_version)) {
		err = -EPROTO;
		goto fail;
	}
	/* The getter returns copied length; the log is at most a 20-byte prefix. */
	firmware_version[err] = '\0';

	/* Publish only acknowledged revision data; never invent a u04 fallback. */
	drvr->bus_if->chip_version = chip_version;
	if (drvr->bus_if->chip == WLAND_VER_91_H &&
	    strcmp(rdawlan_firmware_path, "ap"))
		wland_config_and_efuse(ifp);
	drvr->bus_if->chip_ready = 1;
	pr_err("[RDAWLAN_DRIVER] Chip Version:u%02d\n", chip_version);
	pr_err("[RDAWLAN_DRIVER] Firmware Version:%s\n", firmware_version);
	return 0;

fail:
	/* This cold-start path has not published READY or changed cached revision. */
	WLAND_ERR("chip initialization failed: %d\n", err);
	return err;
}
