/**
  扩展一个 自定义 模块
**/

layui.define('jquery', function (exports) { //提示：模块也可以依赖其它模块，如：layui.define('mod1', callback);
    var $ = layui.$;

    var obj = {
        CreateTiming: function ($, form) {
            return Timing($, form);
        },
        TimeGroupToString: function (TimeGroup) {
            var sTimeGroup = '';
            for (var i = 1; i < 8; i++) {
                var sWeekLangTypeIndex = 29 + (i - 1);

                var sWeekName = getLanguage("welcome.w" + sWeekLangTypeIndex);
                var sWeekDetail = TimeGroup["Week" + i];
                if (sWeekDetail.length > 0) {
                    sTimeGroup += sWeekName + ':' + sWeekDetail + ' ;  ';
                }
            }
            return sTimeGroup;
        }
    }

    //输出 mymod 接口
    exports('faceTiming', obj);
});


function Timing($, form) {

    /**
     * 时段数据集合
     */
    var WeekDays = [];
    /**
     * 切换时段按钮的名称的前缀 
     */
    var WeekName = "TimeGroup";
    /**
     * 当前时段的id
     */
    var iCurrentWeekid = 1;
    /**
     * 表单名称
     */
    var formName = "TimeGroup_edit_div_filter";
    /**
     * 当前拷贝的时段信息
     */
    var oSourceTimeDetail = null;
    //var form = layui.form;
    //var $ = layui.$;
    var obj = {
        name: "",
        init: function (sFormName, weekName, timeGroup, laydate) {
            WeekName = weekName;

            formName = sFormName;

            for (var i = 1; i < 8; i++) {
                WeekDays[i] = timeGroup["Week" + i];
            }
            /**
             * 时段切换点击事件
             */
            $('div[lay-filter="' + sFormName + '"] [name=' + WeekName + 'Week]').on('click', function (p) {
                //   debugger
                var target = $(p.currentTarget);
                var weekid = target.attr("weekid");
                if (!saveWeekDetail())
                    return;
                showWeekDetail(weekid);
                return false;
            });
            /**
             * 拷贝时段
             */
            $('div[lay-filter="' + sFormName + '"] [name=' + WeekName + 'Copy]').on('click', function (p) {
                if (!saveWeekDetail()) return;

                oSourceTimeDetail = form.val(formName);
                return false;
            });
            /**
             * 黏贴时段
             */
            $('div[lay-filter="' + sFormName + '"] [name=' + WeekName + 'Paste]').on('click', function (p) {
                if (oSourceTimeDetail == null) {
                    layer.alert(getLanguage('TimeGroup.t46'));
                    return false;
                }
                form.val(formName, oSourceTimeDetail);
                return false;
            });
            /**
             * 时段清空
             */
            $('div[lay-filter="' + sFormName + '"] [name=' + WeekName + 'Clear]').on('click', function (p) {
                ClearCurrentDayTime();

                return false;
            });
            /**
             * 清空所有时段
             */
            $('div[lay-filter="' + sFormName + '"] [name=' + WeekName + 'ClearAll]').on('click', function (p) {
                ClearCurrentDayTime();
                for (var i = 1; i <= 7; i++) {
                    WeekDays[i] =
                        '';
                }
                return false;
            });
            /**
             * 设置测试数据
             */
            $('div[lay-filter="' + sFormName + '"] [name=' + WeekName + 'TestData]').on('click', function () {
                var oWeekDayDetail = {};

                var dBegin = dayjs().add(1, 'minute');

                for (var i = 1; i <= 8; i++) {

                    oWeekDayDetail[WeekName + "_blockBegin_" + i] = dBegin.format("HH:mm");
                    dBegin = dBegin.add(1, 'minute');
                    oWeekDayDetail[WeekName + "_blockEnd_" + i] = dBegin.format("HH:mm");
                    dBegin = dBegin.add(2, 'minute');
                }
                form.val(formName, oWeekDayDetail);
                saveWeekDetail();
                var sTimeDetail = WeekDays[iCurrentWeekid];
                for (var i = 1; i <= 7; i++) {
                    WeekDays[i] = sTimeDetail;
                }
                return false;
            });


            $('div[lay-filter="' + sFormName + '"] input[type="text"]').on('input', function (event) {
                var inputbox = event.currentTarget;
                var value = inputbox.value;

                var numTable = [];
                for (var i = 0; i < 10; i++) {
                    numTable[i] = 1;
                }
                numTable[":"] = 1;
                var separatorCount = 0;
                var hour = "", minute = "";
                
                if (value.length > 0) {
                    var iSize = value.length;
                    for (var i = 0; i < iSize; i++) {
                        var char = value.slice(i, i + 1);
                        if (char == "：") {
                            separatorCount++;
                            if (separatorCount > 1) {
                                inputbox.value = value.slice(0, i);
                            }
                            else {
                                inputbox.value = value.slice(0, i) + ":";
                            }

                            if (i == 0) {
                                inputbox.value = "";
                            }
                            
                            return;
                        }
                        if (char == ":") {
                            separatorCount++;
                            if (separatorCount > 1) {
                                inputbox.value = value.slice(0, i);
                                return;
                            }
                            if (i == 0) {
                                inputbox.value = "";
                            }
                        }

                        if (numTable[char] != 1) {
                            inputbox.value = value.slice(0, i);
                            return;
                        }


                    }
                    
                    if (separatorCount == 0 && value.length > 2) {

                        if (iSize > 4) iSize = 4;
                        iSize -= 2;
                        inputbox.value = value.slice(0, 2) + ":" + value.slice(2, 2 + iSize);
                        value = inputbox.value;
                        separatorCount = 1;
                    }

                    if (separatorCount == 1) {

                        var sNums = value.split(":");
                        
                        hour = Number(sNums[0]);
                        minute = Number(sNums[1]);
                        
                        if (hour > 23) {
                            inputbox.value = "";
                            return;
                        }
                        if (minute > 59) {
                            inputbox.value = hour + ":";
                            return;
                        }

                    }
                    else if (separatorCount > 1) {
                        inputbox.value = "";
                    }

                }



            });
            $('div[lay-filter="' + sFormName + '"] input[type="text"]').on('blur', function (event) {
                var inputbox = event.currentTarget;
                var value = inputbox.value;
  
                var separatorCount = 0;
                var hour = "", minute = "";

                if (value.length > 0)
                {
                    var iSize = value.length;
                    for (var i = 0; i < iSize; i++) {
                        var char = value.slice(i, i + 1);
                        if (char == ":") {
                            separatorCount++;
                        }
                    }

                    if (separatorCount == 0) {

                        inputbox.value = "00:00";
                        return;
                    }

                    if (separatorCount == 1) {

                        var sNums = value.split(":");

                        hour = Number(sNums[0]);
                        minute = Number(sNums[1]);
                        if (hour < 10 && minute < 10) {
                            inputbox.value = "0" + hour + ":0" + minute;
                            return;
                        }
                        if (hour < 10) {
                            inputbox.value = "0" + hour + ":" + minute;
                            return;
                        }

                        if (minute < 10) {
                            inputbox.value = hour + ":0" + minute;
                            return;
                        }
                    }

                }
                else
                {
                    inputbox.value = "00:00";
                }
            });
            
            for (var i = 1; i <= 8; i++) {
                laydate.render({
                    elem: 'div[lay-filter="' + sFormName + '"] input[name="' + WeekName + "_blockBegin_" + i  +'"]', //指定元素 
                    type: 'time',
                    format: 'HH:mm'
                });
                laydate.render({
                    elem: 'div[lay-filter="' + sFormName + '"] input[name="' + WeekName + "_blockEnd_" + i + '"]', //指定元素 
                    type: 'time',
                    format: 'HH:mm'
                });
            }

            showWeekDetail(1);
        },
        getWeekDetail: function () {
            if (!saveWeekDetail()) return;
            var TimeGroupAll = {};
            for (var i = 1; i < 8; i++) {
                TimeGroupAll["Week" + i] = WeekDays[i];
            }
            return TimeGroupAll;
        },
        SaveTimeGroup: function () {
            return saveWeekDetail();
        }
    };
    /**
     * 清空时段
     */
    function ClearCurrentDayTime() {
        var oWeekDayDetail = {};
        for (var i = 1; i <= 8; i++) {
            oWeekDayDetail[WeekName + "_blockBegin_" + i] = "00:00";
            oWeekDayDetail[WeekName + "_blockEnd_" + i] = "00:00";
        }
        form.val(formName, oWeekDayDetail);
    };
    /**
       * 显示时段
       * @param {any} weekid
       */
    function showWeekDetail(weekid) {

        $('div[lay-filter="' + formName + '"] [name=' + WeekName + 'Week]').removeClass("layui-btn-normal").addClass("layui-btn-primary");
        $('div[lay-filter="' + formName + '"] [name=' + WeekName + 'Week][weekid=' + weekid + ']').removeClass("layui-btn-primary").addClass(
            "layui-btn-normal"); //周一至周六按钮点击后的颜色

        var oWeekDayDetail = {};
        for (var i = 0; i < 8; i++) {
            oWeekDayDetail[WeekName + "_blockBegin_" + (i + 1)] = "00:00";
            oWeekDayDetail[WeekName + "_blockEnd_" + (i + 1)] = "00:00";
        }


        var weekDetail = WeekDays[weekid];
        if (weekDetail.length > 0) {

            var blocks = weekDetail.split("/");

            for (var i = 0; i < blocks.length; i++) {
                var times = blocks[i].split("-");
                oWeekDayDetail[WeekName + "_blockBegin_" + (i + 1)] = times[0];
                oWeekDayDetail[WeekName + "_blockEnd_" + (i + 1)] = times[1];
            }
        }

        form.val(formName, oWeekDayDetail);
        iCurrentWeekid = weekid;
    }
    /**
     * 保存当前时段
     */
    function saveWeekDetail() {
        if (iCurrentWeekid == 0) return;
        var oWeekDayDetail = form.val(formName);
        var dayDetail = [];
        for (var i = 1; i <= 8; i++) {
            var times = [];
            var sBeginTime = oWeekDayDetail[WeekName + "_blockBegin_" + i];
            var sEndTime = oWeekDayDetail[WeekName + "_blockEnd_" + i];

            sBeginTime = FillTime(sBeginTime);
            sEndTime = FillTime(sEndTime);

            if (sBeginTime != '00:00')
                //进行参数检查
                if (!checkTimeFormat(sBeginTime)) return false;
            if (sEndTime != '00:00')
                if (!checkTimeFormat(sEndTime)) return false;
            if (!reducedtime(sBeginTime, sEndTime)) {
                return false;
            }

            if (sBeginTime == '00:00' && sEndTime == '00:00') continue;

            times.push(sBeginTime);
            times.push(sEndTime);

            dayDetail.push(times.join("-"));
        }

        var weekDetail = dayDetail.join("/");


        WeekDays[iCurrentWeekid] = weekDetail;
        return true;
    }

    /**
     * 补全时间格式
     * @param {any} sTime 起始时间
     * @returns 修正后的时间格式
     */
    function FillTime(sTime) {
        sTime = sTime.replace("：", ":");
        var sNums = sTime.split(":");
        if (sNums.length == 2) {

            for (var i = 0; i < 2; i++) {
                if (sNums[i].length == 1)
                    sNums[i] = '0' + sNums[i];
            }

            sTime = sNums.join(":");

        }
        return sTime

    }


    /**
     * 时段对比
     * @param {any} sBeginTime 起始时间
     * @param {any} sEndTime 截止时间
     * @returns 对比结果
     */
    function reducedtime(sBeginTime, sEndTime) {
        if (sBeginTime != sEndTime) {
            var dBegin = dayjs('2021-07-20 ' + sBeginTime + ':00');
            var dEnd = dayjs('2021-07-20 ' + sEndTime + ':00');
            var bisBefore = dBegin.isBefore(dEnd, "minute") // 默认毫秒
            if (!bisBefore) {
                layer.alert(getLanguage('TimeGroup.t47') + sBeginTime + ' - ' + sEndTime, { icon: 2 });
                return false;
            }
        }
        return true;
    }
    /**
     * 检查时段格式
     * @param {any} strTime
     * @returns
     */
    function checkTimeFormat(strTime) {
        //检查时间格式
        var bCheck = true;
        //debugger;
        if (strTime.length == 0) {
            bCheck = false;
        } else {
            if (bCheck && strTime.length != 5) {
                bCheck = false;
            } else {
                if (bCheck) {
                    var sNums = strTime.split(":");
                    if (sNums.length != 2) {
                        bCheck = false;
                    }
                    if (bCheck) {
                        if (sNums[0].length != 2) {
                            bCheck = false;
                        } else {
                            //数字范围判断
                            if (isNaN(sNums[0])) {
                                bCheck = false;
                            } else {
                                var n = Number(sNums[0]);
                                if (n > 23 || n < 0) {
                                    bCheck = false;
                                }
                            }
                        }
                    }
                    if (bCheck) {
                        if (sNums[1].length != 2) {
                            bCheck = false;
                        } else {
                            if (isNaN(sNums[1])) {
                                bCheck = false;
                            } else {
                                var n = Number(sNums[1]);
                                if (n > 59 || n < 0) {
                                    bCheck = false;
                                }
                            }
                        }
                    }


                }
            }
        }
        if (!bCheck) {
            layer.alert(getLanguage('TimeGroup.t48'), { icon: 2 });
        }
        return bCheck;
    }
    return obj;
};