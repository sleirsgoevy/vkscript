// присваивает переменной a результат поиска по фотографиям с данными параметрами
var a = API.photos.search({"q":"Nature","count":3});

// присваивает переменной b список владельцев найденных фотографий
var b = a.items@.owner_id;

// присваивает переменной с данные о страницах владельцев из списка b
var c = API.users.get({"user_ids":b});

// возвращает список фамилий из данных о владельцах
return c@.last_name;

// пример цикла
var a = 1;
var b = 10;
while (b != 0) {
    b = b - 1;
    a = a + 1;
};
return a;
