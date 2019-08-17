var test1, test2, test3, test4, test5, test6, test7;
test1 = 1000000000 + 2000000000; // overflows to -1294967296
{
    var x = [1, 2];
    var y = x;
    x.pop();
    test2 = y.length - x.length; //1; y is still [1, 2]
}
test3 = ({a: 1, b: 2, c: 3}.length); //3
{
    var x = [1, 2, 3];
    x.test = 123;
    test4 = x.length; //4
}
{
    var x = [1, 2, 3];
    var y = [];
    y.push(x.length); //3
    x.length = 1;
    y.push(x.length); //1
    x.push(4);
    y.push(x.length); //still 1
    test5 = y;
}
{
    var x = [1, 2, 3];
    x.test = 123;
    x.pop(); //removes test
    test6 = x.test; //null
}
{
    var x = [1];
    x.push(x.pop());
    test7 = x.length; //2; x = [1, 1]
}
return [test1, test2, test3, test4, test5, test6, test7];
