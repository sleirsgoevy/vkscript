var code = '1;';
var low = -1;
var high = 9997;
var bigstring = '~';
var i = 0;
while(i < 14)
{
    i = i + 1;
    bigstring = bigstring + bigstring;
}
bigstring = bigstring.substr(0, 9996)+"1;";

if(API.execute({code: code+"return true;"})){}
else return -1;

while(high - low > 1)
{
    var mid = (high + low) >> 1;
    var code2 = bigstring.substr(mid, bigstring.length - mid)+code+"return true;";
    var ans = API.execute({code: code2});
    if(ans)
        high = mid;
    else
        low = mid;
}
return high;
