layui.define(['jquery', 'table', 'layer', 'miniPage', 'faceAPI', 'faceTiming'], function (exports) {

    var $ = layui.$;
    var table = layui.table;
    var layer = layui.layer;
    var miniPage = layui.miniPage;
    var openWH = miniPage.getOpenWidthHeight();
    var faceAPI = layui.faceAPI;
    var obj = {
        tableElemID: 'tableElevator',
        LoadTable(tableId, toolbarId, rowtoolbarId) { //加载表格

            var num = getLanguage('Elevator.e3');
            var releaseTime = getLanguage('Elevator.e4');
            var use = getLanguage('Elevator.e5');
            var RelayType = getLanguage('Elevator.e16');//继电器类型
            var RelayType_1 = getLanguage('Elevator.e16_1');//COM & NC 常闭
            var RelayType_2 = getLanguage('Elevator.e16_2');//COM & NO 常闭
            var open = getLanguage('Elevator.e6');
            var open1 = getLanguage('Elevator.e7');
            var open2 = getLanguage('Elevator.e8');
            var open3 = getLanguage('Elevator.e9');
            var timegroup = getLanguage('Elevator.e10');
            var use1 = getLanguage('Elevator.e11');
            var use2 = getLanguage('Elevator.e12');
            tableElemID = tableId;
            //加载表格
            table.render({
                elem: "#" + tableId,
                toolbar: '#' + toolbarId,
                data: [],
                cols: [[
                    { type: 'checkbox' },
                    { field: 'Num', title: num, width: 100 },
                    {
                        field: 'ReleaseTime', title: releaseTime, width: 150, templet: function (d) {

                            return d.ReleaseTime + '（s）';

                        }
                    },
                    {
                        field: 'RelayType', title: RelayType, width: 150, templet: function (d) {

                            if (d.RelayType == 1) {
                                return RelayType_1;//COM & NC 常闭
                            } else {
                                return RelayType_2;//COM & NO 常闭
                            }
                        }
                    },
                    {
                        field: 'TimingOpen_Use', title: use, width: 150, templet: function (d) {

                            if (d.TimingOpen.Use == 1) {
                                return use1;
                            } else {
                                return use2;
                            }
                        }
                    },
                    {
                        field: 'TimingOpen_Timegroup', title: timegroup, width: 400, templet: function (d) {

                            if (d.TimingOpen.Use == 1) {
                                return layui.faceTiming.TimeGroupToString(d.TimingOpen.Timegroup);
                            }
                            else
                                return '';

                        }
                    },
                    {
                        title: getLanguage('Report.r49'),//操作
                        width: 100,
                        toolbar: '#' + rowtoolbarId,
                        align: "center"
                    }

                ]],
                height: openWH[1] - 200,
                limit: 64,
                page: false
            });
            //监听行工具事件

            
            //头工具栏事件
            table.on('tool(' + tableId + 'Filter)', function (obj) {
                var content = miniPage.getHrefContent('page/device/elevator/editelevator.html');
                faceAPI.TimeGroupEditPage = obj.data; //向layer页面传值，传值主要代码
                faceAPI.ElevatorTimeGroupEditResult = null;
                var index = layer.open({
                    title: getLanguage('Elevator.e13'),
                    type: 1,
                    shade: 0.2,
                    maxmin: true,
                    shadeClose: true,
                    area: ['1000px', '920px'],
                    content: content,
                    end: function (layero, index) {

                        if (faceAPI.ElevatorTimeGroupEditResult.result == true) {

                            var result = faceAPI.ElevatorTimeGroupEditResult;
                            var oldDatas = layui.table.cache[tableId];
                            var port = oldDatas.find(d => { return d.Num == obj.data.Num });

                            if (port != undefined) {
                                port.RelayType = result.RelayType;
                                port.ReleaseTime = result.ReleaseTime;
                                port.TimingOpen.Use = result.TimingOpen_Use;
                                port.TimingOpen.Open = result.TimingOpen_Open;
                                port.TimingOpen.Timegroup = result.Timegroup;
                            }
                            table.reload(tableId, { data: oldDatas });
                            //obj.LoadLanguage();
                        }
                    }
                });
            });




        },
        LoadData(elevatorPorts) {

            var datas = [];
            for (var i = 1; i <= 64; i++) {

                var port = elevatorPorts.find(o => { return o.Num == i });
                if (port == undefined) {
                    datas.push({
                        Num: i,
                        RelayType: 1,
                        ReleaseTime: 3,
                        TimingOpen: {
                            Open: 3,
                            Timegroup: {
                                Week1: "",
                                Week2: "",
                                Week3: "",
                                Week4: "",
                                Week5: "",
                                Week6: "",
                                Week7: ""
                            }
                        }
                    });
                } else {
                    datas.push(port);
                }
            }
            table.reload(tableElemID, { data: datas });
            obj.LoadLanguage();
        },
        GetData() {
            var retMap = [];

            var oldDatas = layui.table.cache[tableElemID];
            var DataLength = oldDatas.length;
            for (var i = 0; i < DataLength; i++) {
                var port = oldDatas[i];
                var retObj = {};
                retObj.Num = port.Num;
                retObj.RelayType = port.RelayType;
                retObj.ReleaseTime = port.ReleaseTime;
                retObj.TimingOpen = port.TimingOpen;
                retMap.push(retObj);
            }
            return retMap;
        },
        BatchSet: function () {
            //批量设置

            var checkStatus = table.checkStatus(tableElemID),
                selectItems = checkStatus.data;
            if (selectItems.length == 0) {
                layer.msg(getLanguage('Elevator.BatchSetErrTip1'));
                return;

            }

            //开始批量设置
            var content = miniPage.getHrefContent('page/device/elevator/editelevator.html');
            faceAPI.TimeGroupEditPage = selectItems[0]; //向layer页面传值，传值主要代码
            faceAPI.ElevatorTimeGroupEditResult = null;
            var index = layer.open({
                title: getLanguage('Elevator.e13'),
                type: 1,
                shade: 0.2,
                maxmin: true,
                shadeClose: true,
                area: ['1000px', '920px'],
                content: content,
                end: function (layero, index) {

                    if (faceAPI.ElevatorTimeGroupEditResult.result == true) {

                        var result = faceAPI.ElevatorTimeGroupEditResult;
                        var oldDatas = layui.table.cache[tableElemID];
                        var DataLength = oldDatas.length;
                        for (var i = 0; i < DataLength; i++) {
                            var port = oldDatas[i];
                            if (port['LAY_CHECKED'] == true) {
                                port.RelayType = result.RelayType;
                                port.ReleaseTime = result.ReleaseTime;
                                port.TimingOpen.Use = result.TimingOpen_Use;
                                port.TimingOpen.Open = result.TimingOpen_Open;
                                port.TimingOpen.Timegroup = result.Timegroup;
                            }
                        }
                        table.reload(tableElemID, { data: oldDatas });
                        //obj.LoadLanguage();
                    }
                }
            });

        },
        LoadLanguage: function () {
            setLanguage();
            setAllAttrVal();
        }

    };
    // 工具栏事件
    exports('tableElevator', obj);
});