/*
    我爱模板网 www.5imoban.net
*/

// 语言设置
const languageMap = {
    cn: ChinaLang,
    en: EnglighLang,
    zh_hk: TraditionalChineseLang
}
var curLaguage = null;
var languageDeviceSN = '';

function SetLanguageDeviceSN(sn) {
    languageDeviceSN = sn;
    for (let key in languageMap) {
        languageMap[key].DeviceSN = sn;
        // debugger

    }
    localStorage.setItem('DeviceSN', sn);
}

function getLanguageDeviceSN() {
    
    if (languageDeviceSN == '') {
        languageDeviceSN = localStorage.getItem("DeviceSN");
    }
    return languageDeviceSN;
}
// console.log('[ languageMap ] >', languageMap)
function changeLanguage(language) {
    localStorage.setItem('language', language);

    for (let key in languageMap) {
        if (key === language) {

            break;
        }
        // debugger

    }
    setLanguage();
    setAllAttrVal()
    // 切换语言刷新一下
    try {
        location.reload()
    } catch (error) {

    }

}

function setLanguage() {
    let elements = document.querySelectorAll('[language]');
    let languageType = localStorage.getItem('language') || 'en';
    var language = null;
    for (let key in languageMap) {
        if (key === languageType) {
            language = languageMap[key];
            break;
        }
    }
    curLaguage = language;

    document.querySelector('#languageStatus').innerText = language.description;

    try {
        if (languageType == 'cn') {
            dayjs.locale('zh-cn') // 全局使用简体中文
        } else if (languageType == 'en') {
            dayjs.locale('en') // 全局使用英文
        } else if (languageType == 'zh_hk') {
            dayjs.locale('zh-hk') // 全局使用繁体
        }
    } catch (error) {
        // console.log('[ error ] >', error)
    }

    document.title = languageDeviceSN + ' ' + language["title"];

    for (let i = 0; i < elements.length; i++) {
        let curLanVal = elements[i].getAttribute('language');

        try {

            if (curLanVal.split('.').length > 1) {
                let arr = curLanVal.split('.');
                elements[i].innerText = language[arr[0]][arr[1]];
            } else {
                elements[i].innerText = language[curLanVal];
            }
            //console.log(curLanVal, ' >', elements[i].innerText)
        } catch (error) {
            // console.log('[ error ] >', error)
        }

    }
}

function getCurrentLanguage() {
    if (curLaguage == null) {
        let languageType = localStorage.getItem('language') || 'en';
        var language = null;
        for (let key in languageMap) {
            if (key === languageType) {
                language = languageMap[key];
                break;
            }
        }
        curLaguage = language;
    }
    return curLaguage;
}
function getLanguage(param) {

    getCurrentLanguage();

    let lang;
    try {
        if (param.split('.').length > 1) {
            let arr = param.split('.');
            lang = curLaguage[arr[0]][arr[1]];
        } else {
            lang = curLaguage[param];
        }
        //console.log(param, ' >', lang)
        return lang;
    } catch (error) {
        // console.log('[ error ] >', error)
        return param;
    }

}

//设置所以标签 使用 id 和 data-lang  的值为多语言 id="Login.l3" data-lang='placeholder'
function setAllAttrVal() {
   
    let obj = document.querySelectorAll('[data-lang]');
    // console.log('[ obj ] >', obj)
    for (let i = 0; i < obj.length; i++) {
        let json = {}
        let ele = obj[i];
        let id = obj[i].id;
        json.id = obj[i].id.split(',');
        json.attr = obj[i].dataset.lang.split(',');

        json.attr.forEach((attrName, index) => {
            ele.setAttribute(attrName, getLanguage(json.id[index]));
        });

    }
}

function setAttrVal(id, attr) {
    document.getElementById(id).setAttribute(attr, getLanguage(id))
}

