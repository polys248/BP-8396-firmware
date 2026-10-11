layui.define(['jquery', 'table', 'layer', 'form'], function (exports) {

    var $ = layui.$;
    var table = layui.table;
    var layer = layui.layer;
    var form = layui.form;
    var obj = {
        LoadTable(tableId, toolbarId, maxDataLength) { //加载表格
            var rowId = 0;

            var fieldId = getLanguage("Authcomposition.a5");
            var fielduserCode = getLanguage("Authcomposition.a6");
            //加载表格
            table.render({
                elem: "#" + tableId,
                data: [],
                toolbar: "#" + toolbarId,
                cols: [[
                    { type: 'checkbox' },
                    { field: 'id', title: fieldId, width: 150 },
                    { field: 'userCode', title: fielduserCode, width: 280, edit: true },
                ]],
                height: 400,
                limit: 200
            });
            //工具栏按钮
            table.on('toolbar(' + toolbarId + ')', function (obj) {
                switch (obj.event) {
                    case "add":
                        AddRow(obj);
                        break;
                    case "delete":
                        DeleteRows(obj);
                        break;
                    default:
                        break;
                }
            });
            // 单元格编辑事件
            table.on('edit(' + toolbarId + ')', function (obj) {
                var field = obj.field; // 得到字段
                var value = obj.value; // 得到修改后的值
                var data = obj.data; // 得到所在行所有键值

                var tips1 = getLanguage("Authcomposition.a7");
                var tips2 = getLanguage("Authcomposition.a8");
                var tips3 = getLanguage("Authcomposition.a9");
                // 值的校验
                if (field === 'userCode') {
                    if (!/^\d+$/.test(obj.value)) {
                        layer.tips(tips1, this, { tips: 1 });
                        return; // 重新编辑 -- v2.8.0 新增
                    }
                }
                var rId = data["id"];
                var oldDatas = layui.table.cache[tableId];
                if (oldDatas.findIndex((o) => { return o.userCode === value && o.id != rId }) >= 0) {
                    layer.tips(tips2, this, { tips: 1 });
                    return;
                }
                // 编辑后续操作，如提交更新请求，以完成真实的数据更新
                layer.msg(tips3, { icon: 1 });
            });

            //删除选中行
            function DeleteRows(obj) {
                var id = obj.config.id;
                var checkStatus = table.checkStatus(id);
                var data = checkStatus.data;
                var oldDatas = layui.table.cache[id];
                var newDatas = [];
                rowId = 0;
                for (var i = 0; i < oldDatas.length; i++) {
                    var curObj = oldDatas[i];
                    if (data.findIndex((obj) => { return obj.id === curObj.id }) < 0) {
                        curObj.id = ++rowId;
                        newDatas.push(curObj);
                    }
                }
                table.reload(id, { data: newDatas });
                obj.LoadLanguage();
            }
            //添加行数据
            function AddRow(obj) {
               
                var id = obj.config.id;
                var oldDatas = layui.table.cache[id];
              //  debugger
                if (oldDatas.length < maxDataLength) {
                    rowId = oldDatas.length;
                    oldDatas.push({
                        id: ++rowId,
                        userCode: ""
                    });
                    table.reload(id, { data: oldDatas });
                    obj.LoadLanguage();
                } else {
                    var msg = getLanguage("Authcomposition.a10");
                    layer.msg(msg);
                }
            }
        },
        GetDatas(tableId) { //获取表格数据
            var oldDatas = layui.table.cache[tableId];
            var data = [];
            for (var i = 0; i < oldDatas.length; i++) {
                var id = parseInt(oldDatas[i].userCode);
                if (id == null) {
                    return;
                }
                data.push(id);
            }
            return data;
        },
        ClearData(tableId) { //清空表格数据
            rowId = 0;
            table.reload(tableId, { data: [] });
            obj.LoadLanguage();
        },
        AddRows(tableId, newdata) {//添加多行

            var rowId = 0;
            var data = [];
            for (var i = 0; i < newdata.length; i++) {
                data.push({
                    id: ++rowId,
                    userCode: newdata[i]
                });
            }
            table.reload(tableId, { data: data });
            obj.LoadLanguage();
        },
        LoadSelectChange(id, callback) {
            //AB组组号下拉框改变时触发
            form.on('select(' + id + ')', function (data) {
                callback(parseInt(data.value));
            });


        },
        LoadLanguage: function () {
            setLanguage();
            setAllAttrVal();
        }

    }

    // 工具栏事件
    exports('tableTeam', obj);
});