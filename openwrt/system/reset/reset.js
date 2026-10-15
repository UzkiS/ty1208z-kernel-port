'use strict';
'require view';
'require fs';
'require ui';

return view.extend({
	load: function() {
		return fs.exec('/sbin/ty1208z-reset', [ '--check' ]);
	},
	render: function(result) {
		return E('div', {}, [
			E('h2', {}, '恢复默认设置'),
			E('p', {}, '清除系统配置、管理密码、SSH 登录授权、无线和挂载设置。恢复 root 空密码和 TY1208Z 无密码热点，与网口桥接，由主路由分配地址。'),
			E('p', {}, '保留软件文件、本机 MAC、SSH 主机身份、SD 文件、Docker 镜像和容器数据、用户文件及引导分区。系统配置目录恢复为固件默认内容；新增软件可能需要重新配置或安装。磁盘挂载和容器自启设置也需重新配置。'),
			result.code ? E('pre', {}, result.stderr || '恢复默认预检失败') : '',
			E('button', {
				'class': 'cbi-button cbi-button-negative important',
				'disabled': (result.code !== 0 || !L.hasViewPermission()) || null,
				'click': ui.createHandlerFn(this, function() {
					ui.showModal('确认恢复默认', [
						E('p', {}, '系统将清除配置与登录授权并重启。热点恢复为 TY1208Z，无密码。是否继续？'),
						E('div', { 'class': 'right' }, [
							E('button', { 'class': 'btn', 'click': ui.hideModal }, '取消'),
							' ',
							E('button', { 'class': 'btn cbi-button-negative', 'click': ui.createHandlerFn(this, function() {
								return fs.exec('/sbin/ty1208z-reset', [ '-y', '-r' ]).then(function(res) {
									if (res.code !== 0) throw new Error(res.stderr || '恢复默认失败');
									ui.showModal('正在恢复默认', [ E('p', { 'class': 'spinning' }, '正在重启。请连接 TY1208Z 热点或原网口网络。地址由主路由分配，可在主路由客户端列表中查询。') ]);
									ui.awaitReconnect(window.location.host, 'openwrt.lan');
								}).catch(function(err) {
									ui.hideModal();
									ui.addNotification(null, E('p', {}, err.message));
								});
							}) }, '恢复并重启')
						])
					]);
				})
			}, '恢复默认设置')
		]);
	},
	handleSaveApply: null,
	handleSave: null,
	handleReset: null
});
