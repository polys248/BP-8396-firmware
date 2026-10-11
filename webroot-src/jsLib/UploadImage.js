function ImageUtility() {
    /* //图片上传，将base64的图片转成二进制对象，塞进formdata上传
     function upload() {
       var myformdata = imageBase64ToFormData(myImg);
       if(myformdata==undefined) return;
       
       var xhr = new XMLHttpRequest();
       
   
       //上传压缩图片至服务器
       xhr.open('post', '/imgUpload/upload.do?fileType=');
       
       xhr.onreadystatechange = function() {
         if (xhr.readyState == 4 && xhr.status == 200) {
           var jsonData = JSON.parse(xhr.responseText);
           var text = jsonData.path ? '上传成功' : '上传失败';
   
           console.log(text + '：' + jsonData.path);
           
           //回调页面方法
           callbackUpload(jsonData.path);
   
         }
       };
   
       xhr.send(myformdata);
     }*/

    var obj = {
        UploadImageMaxSize: 30 * 1024,
        imageMaxHeight: 960,//最大高度
        imageMaxWidth: 720,//最大宽度
        getImageTypeOnSrc: function (srcType) {
            var slist = srcType.split(";")[0];
            return slist.split(":")[1];

        },
        //获取压缩的图片 input 的file对象
        getCompressImage: function (file, imgElement, overfunc) {
            //检查文件类型是否为图片
            if (!/\/(?:jpeg|png|gif|bmp)/i.test(file.type)) {
                imgElement.src = "";
                return false;
            }

            //加载图片文件
            var reader = new FileReader();
            reader.onload = function () {
                var result = this.result;
                var img = new Image();
                img.onload = function () {

                    //图片加载完毕之后进行压缩
                    var data = this.compressImage(img);
                    imgElement.src = data.data;

                    $(imgElement).attr("imgType", "");
                    if (overfunc) overfunc();

                    if (overfunc) {
                        var srt = imgElement.src.split(",");
                        var filedata = window.atob(srt[1]);
                        overfunc(this.getImageTypeOnSrc(srt[0]), filedata.length);
                    }



                };
                img.src = result;
            };

            reader.readAsDataURL(file);
            return true;
        },


        //使用canvas对大图片进行压缩
        compressImage: function (img) {
            // 用于压缩图片的canvas
            var canvas = document.createElement("canvas");
            var ctx = canvas.getContext('2d');

            //瓦片canvas
            var tCanvas = document.createElement("canvas");
            var tctx = tCanvas.getContext("2d");


            var initSize = img.src.length;
            var width = img.width;
            var height = img.height;
            var resultObj = {};
            resultObj.width = width;
            resultObj.height = height;
            resultObj.initSize = initSize;
            resultObj.initWidth = width;
            resultObj.initHeight = height;
            resultObj.ratio = 0;
            //console.log("压缩前图像尺寸："  + width + "*" + height);

            if (height <= this.imageMaxHeight && width < this.imageMaxWidth) {
                //console.log("图片不需要压缩");
                //console.log(img.src);
                resultObj.data = img.src;
                resultObj.length = img.src.length;
                return resultObj;
            }

            if (height > this.imageMaxHeight) {
                var oldHeight = height;
                height = this.imageMaxHeight;
                width = height * (width / oldHeight); //画面的宽高比必须等于被压缩图片的宽高比
            }


            if (width > this.imageMaxWidth) {
                var oldWidth = width;
                width = this.imageMaxWidth;
                height = width * (height / oldWidth); //画面的宽高比必须等于被压缩图片的宽高比
            }


            //如果图片大于四百万像素，计算压缩比并将大小压至400万以下
            var ratio = width * height / 4000000;
            if (ratio > 1) {
                ratio = Math.sqrt(ratio);
                width /= ratio;
                height /= ratio;
            } else {
                ratio = 1;
            }
            //初始化画布大小
            canvas.width = width;
            canvas.height = height;
            //console.log("压缩后图像尺寸："  + width + "*" + height);
            //铺底色
            ctx.fillStyle = "#fff";
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            //如果图片像素大于100万则使用瓦片绘制
            var count = width * height / 1000000;
            if (count > 1) {
                count = ~~(Math.sqrt(count) + 1); //计算要分成多少块瓦片

                //计算每块瓦片的宽和高
                var nw = ~~(width / count);
                var nh = ~~(height / count);

                tCanvas.width = nw;
                tCanvas.height = nh;

                for (var i = 0; i < count; i++) {
                    for (var j = 0; j < count; j++) {
                        tctx.drawImage(img, i * nw * ratio, j * nh * ratio, nw * ratio, nh * ratio, 0, 0, nw, nh);
                        ctx.drawImage(tCanvas, i * nw, j * nh, nw, nh);
                    }
                }
            } else {
                ctx.drawImage(img, 0, 0, width, height);
            }

            //进行最小压缩
            var ndata = canvas.toDataURL('image/jpeg', 1);
            /*
            console.log('压缩前：' + initSize);
            console.log('压缩后：' + ndata.length);
            console.log('压缩率：' + ~~(100 * (initSize - ndata.length) / initSize) + "%");
            */

            resultObj.width = width;
            resultObj.height = height;
            resultObj.data = ndata;
            resultObj.length = ndata.length;
            resultObj.ratio = ~~(100 * (initSize - resultObj.length) / initSize) ;
            tCanvas.width = tCanvas.height = canvas.width = canvas.height = 0;
            //console.log(resultObj);
            return resultObj;
        },


        //将图片元素转换为 FormData 对象
        imageBase64ToFormData: function (imgElement) {
           
            //var imgBolb = this.imageBase64ToBlob(imgElement);
            //var myformdata = this.getFormData();

            //myformdata.append('imagefile', imgBolb);
            //myformdata.append('FileType', sType);
            //myformdata.append('FileSize', buffer.length);

            return myformdata;
        },
        /**
         * base64图片转buffer对象
         * @param {any} imgElement
         * @returns  Buffer
         */
        imageBase64ToBuffer: function (imgElement) {
            var src = imgElement.src;
            if (src.length == 0) {
                return undefined;
            }
            src = src.split(",");

            var sType = this.getImageTypeOnSrc(src[0]);
            var strbase64 = src[1];
            if (strbase64.length == 0) {
                return undefined;
            }

            var filedata = window.atob(strbase64);
            var buffer = new Uint8Array(filedata.length);
            for (var i = 0; i < filedata.length; i++) {
                buffer[i] = filedata.charCodeAt(i);
            }            
            return buffer;
        },
        getFile: function (buffer,id) {

          // var blobParts = buffer;
            var options = { type: 'image/jpg' };
            var fileName = id+'.jpg';

            var blob = new Blob([buffer], options);
            var file = new File([blob], fileName, options);
            return file;
        },

        /**
         * 获取blob对象的兼容性写法
         * @param buffer
         * @param format
         * @returns {*}
         */
        getBlob: function (buffer, format) {
            try {
                return new Blob(buffer, { type: format });
            } catch (e) {
                var bb = new (window.BlobBuilder || window.WebKitBlobBuilder || window.MSBlobBuilder);
                buffer.forEach(function (buf) {
                    bb.append(buf);
                });
                return bb.getBlob(format);
            }
        },

        /**
         * 获取formdata
         */
        getFormData: function () {
            var isNeedShim = ~navigator.userAgent.indexOf('Android')
                && ~navigator.vendor.indexOf('Google')
                && !~navigator.userAgent.indexOf('Chrome')
                && navigator.userAgent.match(/AppleWebKit\/(\d+)/).pop() <= 534;

            return isNeedShim ? new FormDataShim() : new FormData()
        },
        /**
         * formdata 补丁, 给不支持formdata上传blob的android机打补丁
         * @constructor
         */
        FormDataShim: function () {
            console.warn('using formdata shim');
            
            var o = this,
                parts = [],
                boundary = Array(21).join('-') + (+new Date() * (1e16 * Math.random())).toString(36),
                oldSend = XMLHttpRequest.prototype.send;

            this.append = function (name, value, filename) {
                parts.push('--' + boundary + '\r\nContent-Disposition: form-data; name="' + name + '"');

                if (value instanceof Blob) {
                    parts.push('; filename="' + (filename || 'blob') + '"\r\nContent-Type: ' + value.type + '\r\n\r\n');
                    parts.push(value);
                }
                else {
                    parts.push('\r\n\r\n' + value);
                }
                parts.push('\r\n');
            };

            // Override XHR send()
            XMLHttpRequest.prototype.send = function (val) {
                var fr,
                    data,
                    oXHR = this;
                
                if (val === o) {
                    // Append the final boundary string
                    parts.push('--' + boundary + '--\r\n');

                    // Create the blob
                    data = o.getBlob(parts);

                    // Set up and read the blob into an array to be sent
                    fr = new FileReader();
                    fr.onload = function () {
                        oldSend.call(oXHR, fr.result);
                    };
                    fr.onerror = function (err) {
                        throw err;
                    };
                    fr.readAsArrayBuffer(data);

                    // Set the multipart content type and boudary
                    this.setRequestHeader('Content-Type', 'multipart/form-data; boundary=' + boundary);
                    XMLHttpRequest.prototype.send = oldSend;
                }
                else {
                    oldSend.call(this, val);
                }
            };
        }

    }

    return obj;
};
