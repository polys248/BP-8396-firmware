/**
  扩展一个 自定义 模块
**/

layui.define('jquery', function (exports) { //提示：模块也可以依赖其它模块，如：layui.define('mod1', callback);
    var $ = layui.$;
    var obj = {
        storeTableKey: 'FaceWebAPI',//存储数据操作的key值
        jwtTokenKey: 'loginToken',
        SaveJWTToken: function (token) {//保存JWT Token值
            layui.data(this.storeTableKey, { key: this.jwtTokenKey, value: token });
        },
        GetJWTToken: function () {
            var mySetting = layui.data(this.storeTableKey);
            if (mySetting.hasOwnProperty(this.jwtTokenKey) == false) {
                return "";
            }
            return mySetting[this.jwtTokenKey];
        },
        Ajax: function (par) {//
            var sToken = this.GetJWTToken();
            if (sToken == "") return;

            var that = this;
            
            if (par.timeout == undefined) par.timeout = 5000;
            //自定义Ajax
            $.ajax({
                type: par.type,
                url: par.url,
                data: par.data,
                timeout: par.timeout,
                contentType: par.contentType,
                processData: par.processData,
                headers: {
                    //token: par.token,
                    Authorization: "Bearer " + sToken,
                    // ChangLanguage:language
                },
                success: par.success,
                error: par.error,
                complete: par.complete
            });
        },
        AjaxPOSTJson: function (par) {//
            var sToken = this.GetJWTToken();
            if (sToken == "") return;
            
            if (par.timeout == undefined) par.timeout = 60000;
            var that = this;
            //自定义Ajax
            $.ajax({
                type: 'POST',
                url: par.url,
                timeout: par.timeout,
                data: JSON.stringify(par.data),
                contentType: "application/json; charset=utf-8",
                processData: par.processData,
                headers: {
                    //token: par.token,
                    Authorization: "Bearer " + sToken,
                    // ChangLanguage:language
                },
                success: par.success,
                error:par.error,
                complete: par.complete
            });
        },
        GotoLogin: function (showbox) {
            layui.data(this.storeTableKey, null); //删除test表
            if (showbox) {
                //请重新登录！
                layer.alert(getLanguage('Login.relogin'), { icon: 2 }, function () {
                    window.location = 'page/login.html';
                });
            }
            else {
                window.location = 'page/login.html';
            }
        },

        /**
        时间转换
        */
        unixTimeStampToDateString: function (unixTimeStamp) {
            // 转换为毫秒
            var timeStampInMs = unixTimeStamp * 1000;

            // 创建一个 Date 对象
            var date = new Date(timeStampInMs);

            // 获取年、月、日、小时、分钟和秒
            var year = date.getFullYear();
            var month = ('0' + (date.getMonth() + 1)).slice(-2);
            var day = ('0' + date.getDate()).slice(-2);
            var hours = ('0' + date.getHours()).slice(-2);
            var minutes = ('0' + date.getMinutes()).slice(-2);
            var seconds = ('0' + date.getSeconds()).slice(-2);

            // 拼接日期字符串
            var dateString = year + '-' + month + '-' + day + ' ' + hours + ':' + minutes + ':' + seconds;

            return dateString;
        },


        /**
        检查数值类型
        strValue  字符串的数值类型
        maxValue  最大值
        minValue  最小值
        defValue  默认值
        **/
        CheckNumberValue: function (strValue, minValue, maxValue, defValue) {
            if (strValue?.length == 0) {
                return defValue;
            }
            
            var strMax = String(maxValue);
            if (strValue?.length > strMax?.length) {
                return defValue;
            }


            var intValue = parseInt(strValue);

            if (intValue < minValue || intValue > maxValue) {
                return defValue;
            }
            return intValue;
        },
        CheckInputBox: function () {
            var that = this;
            $('input[CheckBytes]').on('input', function (event) {
                var inputbox = event.currentTarget;
                that.CheckInputBoxTextBytes(inputbox);
            });

            $('input[CheckBytes]').on('blur', function (event) {
                var inputbox = event.currentTarget;
                that.CheckInputBoxTextBytes(inputbox);

            });


            $('input[type="number"]').on('input', function (event) {
                var inputbox = event.currentTarget;

                var maxValue = inputbox.max;
                var maxLength = inputbox.maxLength;
                var value = inputbox.value;
                
                if (value.length > 0) {
                    var iSize = value.length;
                    for (var i = 0; i < iSize; i++) {
                        var char = value.slice(i, i + 1);
                        if (char == 'e' || char == 'E') {
                            inputbox.value = value.slice(0, i);
                            break;
                        }
                    }
                }

                if (maxValue.length > 0)
                    maxValue = Number(maxValue);
                else
                    maxValue = undefined;




                if (maxLength > 0) {
                    if (value.length > maxLength) {
                        value = value.slice(0, maxLength);
                        inputbox.value = value;
                    }
                }


                var numValue = Number(value);

                if (maxValue != undefined) {
                    if (numValue > maxValue) {
                        numValue = maxValue;
                        inputbox.value = String(numValue);
                    }
                }


            });
            $('input[type="number"]').on('blur', function (event) {
                var inputbox = event.currentTarget;

                var minValue = inputbox.min;
                var value = inputbox.value;

                if (value.length > 0) {
                    var iSize = value.length;
                    for (var i = 0; i < iSize; i++) {
                        var char = value.slice(i, i + 1);
                        if (char == 'e' || char == 'E' ) {
                            inputbox.value = value.slice(0, i);
                            break;
                        }
                    }
                }


                if (minValue.length > 0)
                    minValue = Number(minValue);
                else
                    minValue = undefined;


                if (value.length == 0 && minValue != undefined) {
                    inputbox.value = String(minValue);
                    return
                }

                if (value.length == 0) {
                    inputbox.value = 0;
                    return
                }

                var numValue = Number(value);

                if (minValue != undefined) {
                    if (numValue < minValue) {
                        numValue = minValue;
                        inputbox.value = numValue;
                    }
                }

            });
            $('input[OnlyNumber]').on('input', function (event) {
                var inputbox = event.currentTarget;
                var value = inputbox.value;

                var numTable = [];
                for (var i = 0; i < 10; i++) {
                    numTable[i] = 1;
                }

                if (value.length > 0) {
                    var iSize = value.length;
                    for (var i = 0; i < iSize; i++) {
                        var char = value.slice(i, i + 1);
                        if (numTable[char] != 1) {
                            inputbox.value = value.slice(0, i);
                            break;
                        }
                    }
                }


            });
            $('input[IPFormat]').on('input', function (event) {
                var inputbox = event.currentTarget;
                var value = inputbox.value;

                var numTable = [];
                for (var i = 0; i < 10; i++) {
                    numTable[i] = 1;
                }
                numTable["."] = 1;

                if (value.length > 0) {
                    var iSize = value.length;

                    for (var i = 0; i < iSize; i++) {
                        var char = value.slice(i, i + 1);
                        if (numTable[char] != 1) {
                            inputbox.value = value.slice(0, i);
                            return;
                        }
                    }

                    var strNum = "";
                    var iNumCount = 0;
                    if (value.length == 0) return;
                    var iMarkCount = 0;
                    for (var i = 0; i < iSize; i++) {
                        var char = value.slice(i, i + 1);
                        if (char == ".") {
                            iMarkCount++;
                            if (iMarkCount > 3) {
                                inputbox.value = value.slice(0, i);
                                break;
                            }

                            if (iNumCount == 0) {
                                inputbox.value = value.slice(0, i);
                                break;
                            }
                            iNumCount = 0;
                            strNum = "";
                            continue;
                        }
                        if (iNumCount == 3) {
                            //需要插入一个点
                            value = value.slice(0, i) + "." + value.slice(i);
                            inputbox.value = value;
                            break;
                        }
                        strNum = strNum + char;
                        iNumCount++;

                        if (iNumCount == 3) {
                            //满3个数字

                            var iNum = Number(strNum);
                            if (iNum > 255) {
                                value = value.slice(0, i - 2)
                                inputbox.value = value;
                                break;
                            }
                        }
                    }
                }


            });
            $('input[IPFormat]').on('blur', function (event) {
                //离开焦点
                var inputbox = event.currentTarget;
                var value = inputbox.value;
                var numTable = [];
                for (var i = 0; i < 10; i++) {
                    numTable[i] = 1;
                }
                numTable["."] = 1;

                if (value.length > 0) {
                    var iSize = value.length;

                    var iMarkCount = 0;
                    for (var i = 0; i < iSize; i++) {
                        var char = value.slice(i, i + 1);
                        if (char == ".") {
                            iMarkCount++;
                        }
                    }

                    if (iMarkCount != 3) {
                        inputbox.value = "0.0.0.0";
                        return;
                    }

                    var sNums = value.split(".");
                    for (var i = 0; i < 4; i++) {
                        var num = Number(sNums[i]);
                        if (num > 255) {
                            inputbox.value = "0.0.0.0";
                            return;
                        }
                        sNums[i] = num;
                    }
                    inputbox.value = sNums.join(".");
                }
                else {
                    inputbox.value = "0.0.0.0";
                }
            });

            $('input[TimeFormat_HHmm]').on('input', function (event) {
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
            $('input[TimeFormat_HHmm]').on('blur', function (event) {
                var inputbox = event.currentTarget;
                var value = inputbox.value;

                var separatorCount = 0;
                var hour = "", minute = "";

                if (value.length > 0) {
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
                else {
                    inputbox.value = "00:00";
                }
            });

            $('input[TimeFormat_YYYYMMDD]').on('input', function (event) {
                var inputbox = event.currentTarget;
                var value = inputbox.value;

                var numTable = [];
                for (var i = 0; i < 10; i++) {
                    numTable[i] = 1;
                }
                numTable["-"] = 1;
                var separatorCount = 0;
                var year = "", month = "", day = "";

                if (value.length > 0) {
                    var iSize = value.length;
                    for (var i = 0; i < iSize; i++) {
                        var char = value.slice(i, i + 1);
                        if (char == "-") {
                            separatorCount++;
                            if (separatorCount > 2) {
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

                    if (separatorCount == 0 && value.length > 4) {
                        inputbox.value = value.slice(0, 4) + "-" + value.slice(4, 4 + iSize);
                        value = inputbox.value;
                        separatorCount = 1;
                    }
                    if (separatorCount == 1 && value.length > 7) {
                        inputbox.value = value.slice(0, 7) + "-" + value.slice(7, 7 + iSize);
                        value = inputbox.value;
                        separatorCount = 2;
                    }

                    if (separatorCount == 2) {

                        var sNums = value.split("-");

                        year = Number(sNums[0]);
                        month = Number(sNums[1]);
                        day = Number(sNums[2]);

                        if (year > 2099) {
                            inputbox.value = "";
                            return;
                        }
                        if (month > 12) {
                            inputbox.value = year + "-";
                            return;
                        }
                        if (day > 31) {
                            inputbox.value = year + "-" + month + "-";
                            return;
                        }


                    }
                    else if (separatorCount > 2) {
                        
                        inputbox.value = dayjs().format("YYYY-MM-DD");
                    }

                }



            });
            $('input[TimeFormat_YYYYMMDD]').on('blur', function (event) {
                var inputbox = event.currentTarget;
                var value = inputbox.value;

                var separatorCount = 0;
                var year = "", month = "", day = "";
                
                if (value.length > 0) {
                    var iSize = value.length;
                    for (var i = 0; i < iSize; i++) {
                        var char = value.slice(i, i + 1);
                        if (char == "-") {
                            separatorCount++;
                            if (separatorCount > 2) {
                                inputbox.value = dayjs().format("YYYY-MM-DD");
                                return;
                            }
                        }
                    }

                    if (separatorCount != 2) {
                        inputbox.value = dayjs().format("YYYY-MM-DD");
                        return;
                    }

                    var sNums = value.split("-");

                    year = Number(sNums[0]);
                    month = Number(sNums[1]);
                    day = Number(sNums[2]);
                    if (year < 100)
                        year = year + 2000;

                    if (year > 2099) {
                        year=2099
                    }
                    if (year < 2000) {
                        year = 2000;
                    }
                    if (month > 12) {
                        month = 12;
                    }
                    if (month < 1)
                        month = 1;

                    if (day > 31) {
                        day=31
                    }
                    if (day < 1) {
                        day = 1
                    }
                    var mydateisValid = dayjs(year + '-' + month + '-' + day).isValid();
                    if (mydateisValid)
                        inputbox.value = dayjs(year + '-' + month + '-' + day).format("YYYY-MM-DD");
                    else
                        inputbox.value = dayjs().format("YYYY-MM-DD");

                }


            });
        },
        CheckInputBoxTextBytes: function (inputbox) {
            var maxLength = inputbox.maxLength;
            var value = inputbox.value;
            var strLen = value.length;

            var encoder = new TextEncoder(); // 创建TextEncoder实例
            var bytes = encoder.encode(value);  // 将字符串转换为UTF-8编码的Uint8Array

            var bUpdateValue = false;

            do {
                if (bytes.length > maxLength) {
                    
                    strLen--;
                    value = value.slice(0, strLen);
                    bytes = encoder.encode(value);
                    bUpdateValue = true;
                    
                }
                else {
                    break;
                }
            } while (true);
            if (bUpdateValue) {
                inputbox.value = value;
            }
            console.log("文本字节数：" + bytes.length)

        },
        ShowMouseTipMessageBox: function (filtername,layer) {
            $("[lay-filter=" + filtername +"] [tipShow=1]").mouseenter(input_mouseenter);
            $("[lay-filter=" + filtername +"] [tipShow=1]").mouseleave(() => {
                if (iMouseenter_TipIndex > 0)
                    layer.close(iMouseenter_TipIndex);
            });
            // 输入框 值范围提示
            var iMouseenter_TipIndex = 0;
            function input_mouseenter() {
                var that = this;
                if (iMouseenter_TipIndex > 0)
                    layer.close(iMouseenter_TipIndex);
                var em = $(that);
                var msg = em.attr("tipMsg");

                iMouseenter_TipIndex = layer.tips(msg, that, {
                    tips: [1, '#000'], // tips风格，[0, '']表示默认风格，1表示自定义风格，'#000'表示背景颜色
                    area: ['400px'] // 设置宽度和高度
                });
            }
        },

    };

    //输出 mymod 接口
    exports('faceAPI', obj);
}); 