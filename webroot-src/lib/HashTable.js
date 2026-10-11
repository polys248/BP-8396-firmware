function HashTable() {
    this.ObjArr = {};
    this.Count = 0;
    //添加 
    this.Add = function (key, value) {
        if (this.ObjArr.hasOwnProperty(key)) {
            return false; //如果键已经存在，不添加 
        } else {
            this.ObjArr[key] = value;
            this.Count++;
            return true;
        }
    }
    //是否包含某项 
    this.Contains = function (key) {
        return this.ObjArr.hasOwnProperty(key);
    }
    //取某一项 其实等价于this.ObjArr[key] 
    this.GetValue = function (key) {
        if (this.Contains(key)) {
            return this.ObjArr[key];
        } else {
            throw Error("Hashtable not cotains the key: " + String(key)); //脚本错误 
            //return; 
        }
    }
    //移除 
    this.Remove = function (key) {
        if (this.Contains(key)) {
            delete this.ObjArr[key];
            this.Count--;
        }
    }
    //清空 
    this.Clear = function () {
        this.ObjArr = {}; this.Count = 0;
    }
};
 /*
           * 
//员工
function employee(id, userName) {
  this.id = id;
  this.userName = userName;
}
function test() {
  var ht = new HashTable();
  var tmpEmployee = null;
  for (var i = 1; i < 6; i++) {
      tmpEmployee = new employee(i, "Employee_" + i);
      ht.Add(i, tmpEmployee);
  }
  for (var i = 1; i <= ht.Count; i++) {
      alert(ht.GetValue(i).userName); //其实等价于ht.ObjArr[i].userName
      //alert(ht.ObjArr[i].userName);
  }
  ht.Remove(1);
  alert(ht.Contains(1)); //false
  alert(ht.Contains(2)); //true
  //alert(ht.GetValue(1)); //异常
  var result = ht.GetValue(2);
  if (result != null) {
      alert("Employee Id:" + result.id + ";UserName:" + result.userName);
  }
  ht.Add(2, "这一个key已经存在!"); //Add无效
  //ht.Clear(); //清空
  alert(ht.Count);
}  

*/