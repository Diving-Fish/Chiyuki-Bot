# 数据来源

## pokedex

直接从 showdown 的 pokedex 获取就行。

## movedex

在 showdown 的 teambuilder 执行如下代码：

```js
const result = {};
function parseResults(resultSingles, resultDoubles) {
    const parsed = {
        'overused': new Set(),
        'useless': new Set()
    }
    let obj = parsed.overused;
    for (const move of resultSingles) {
        if (move[0] == 'header' && move[1] == 'Usually useless moves') {
            obj = parsed.useless;
        }
        else if (move[0] == 'move') {
            obj.add(move[1]);
        }
    }
    for (const move of resultDoubles) {
        if (move[0] == 'header' && move[1] == 'Usually useless moves') {
            obj = parsed.useless;
        }
        else if (move[0] == 'move') {
            obj.add(move[1]);
        }
    }
    parsed.overused = Array.from(parsed.overused);
    parsed.useless = Array.from(parsed.useless).filter(m => !parsed.overused.includes(m));
    return parsed;
}
for (const poke in BattlePokedex) {
    if (poke == '' || BattlePokedex[poke].num < 0) continue;
    for (let i = 9; i >= 7; i--) {
        const bms = new BattleMoveSearch();
        bms.dex.gen = i;
        bms.species = poke;
        const resultSingles = bms.getBaseResults();
        bms.isDoubles = true;
        const resultDoubles = bms.getBaseResults();
        result[poke] = parseResults(resultSingles, resultDoubles);
        if (result[poke].overused.length > 0) break;
    }
}
console.log(JSON.stringify(result));
```

复制输出的结果到 moves.json 即可。

如果要 national dex 可以用如下代码：
```js
const result = {};
const result_nd = {};
function parseResults(resultSingles, resultDoubles) {
    const parsed = {
        'overused': new Set(),
        'useless': new Set()
    }
    let obj = parsed.overused;
    for (const move of resultSingles) {
        if (move[0] == 'header' && move[1] == 'Usually useless moves') {
            obj = parsed.useless;
        }
        else if (move[0] == 'move') {
            obj.add(move[1]);
        }
    }
    for (const move of resultDoubles) {
        if (move[0] == 'header' && move[1] == 'Usually useless moves') {
            obj = parsed.useless;
        }
        else if (move[0] == 'move') {
            obj.add(move[1]);
        }
    }
    parsed.overused = Array.from(parsed.overused);
    parsed.useless = Array.from(parsed.useless).filter(m => !parsed.overused.includes(m));
    return parsed;
}
for (const poke in BattlePokedex) {
    if (poke == '' || BattlePokedex[poke].num < 0) continue;
    for (let i = 9; i >= 7; i--) {
        const bms = new BattleMoveSearch();
        bms.dex.gen = i;
        bms.dex.modid = 'gen9'
        bms.species = poke;
        bms.format = 'ag';
        bms.formatType = 'natdex';
        const resultSingles = bms.getBaseResults();
        result_nd[poke] = parseResults(resultSingles, resultSingles);
        if (result_nd[poke].overused.length > 0) break;
    }
    for (let i = 9; i >= 7; i--) {
        const bms = new BattleMoveSearch();
        bms.dex.gen = i;
        bms.species = poke;
        bms.format = 'ag';
        const resultSingles = bms.getBaseResults();
        bms.isDoubles = true;
        const resultDoubles = bms.getBaseResults();
        result[poke] = parseResults(resultSingles, resultDoubles);
        if (result[poke].overused.length > 0) break;
    }
}
console.log(JSON.stringify({
    gen9: result,
    nationalDex: result_nd
}));
```

## translation.json

从油猴的翻译脚本获取

## move_list.json

`JSON.stringify(BattleMovedex);`

## ability_list.json

`JSON.stringify(BattleAbilities);`