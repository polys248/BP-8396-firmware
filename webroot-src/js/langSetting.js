
function setAllAttrVal(){
  const DataLang = []
  let obj = document.querySelectorAll('[data-lang]')
  for (let i = 0; i < obj.length; i++) {
    let json={}
    json.id = obj[i].id;
    json.attr=obj[i].dataset.lang;
    DataLang.push(json);
    document.getElementById(obj[i].id).setAttribute(json.attr,getLanguage(obj[i].id))
  }
}

function setAttrVal(id,attr){
  document.getElementById(id).setAttribute(attr,getLanguage(id))
}

