// The SQL console's engine: a deliberately small SELECT engine, enough to interrogate
// the run data honestly and small enough to read. Tokeniser, recursive-descent parser,
// evaluator. No page code here, so tests/sqlengine.test.mjs can run it under Node.
// Moved unchanged from the original single-file page, except: runQuery takes the rows
// as an argument instead of reading a global, and COLS includes qid and flagged.

export const COLS = ["qid","v","m","p","t","db","q","gold","sql","ok","ran","silent","err",
            "conf","grows","prows","tok","cost","ms","flagged"];

export function tokenize(s){
  var out = [], i = 0;
  var re = {
    ws:/\s+/y, num:/-?\d+(\.\d+)?/y, str:/'([^']*)'/y,
    op:/(>=|<=|!=|<>|=|>|<)/y, word:/[A-Za-z_][A-Za-z_0-9]*/y, punc:/[(),*]/y
  };
  while(i < s.length){
    var m;
    re.ws.lastIndex=i; if((m=re.ws.exec(s))){ i=re.ws.lastIndex; continue; }
    re.str.lastIndex=i; if((m=re.str.exec(s))){ out.push({t:"str",v:m[1]}); i=re.str.lastIndex; continue; }
    re.num.lastIndex=i; if((m=re.num.exec(s))){ out.push({t:"num",v:parseFloat(m[0])}); i=re.num.lastIndex; continue; }
    re.op.lastIndex=i;  if((m=re.op.exec(s))){ out.push({t:"op",v:m[0]}); i=re.op.lastIndex; continue; }
    re.word.lastIndex=i;if((m=re.word.exec(s))){ out.push({t:"word",v:m[0]}); i=re.word.lastIndex; continue; }
    re.punc.lastIndex=i;if((m=re.punc.exec(s))){ out.push({t:"punc",v:m[0]}); i=re.punc.lastIndex; continue; }
    throw new Error("Cannot read character " + JSON.stringify(s[i]) + " at position " + i);
  }
  return out;
}

function Parser(toks){ this.k = toks; this.i = 0; }
Parser.prototype.peek = function(){ return this.k[this.i]; };
Parser.prototype.next = function(){ return this.k[this.i++]; };
Parser.prototype.isWord = function(w){ var t=this.peek();
  return t && t.t==="word" && t.v.toUpperCase()===w; };
Parser.prototype.eatWord = function(w){ if(this.isWord(w)){ this.i++; return true; } return false; };
Parser.prototype.expectWord = function(w){
  if(!this.eatWord(w)) throw new Error("Expected " + w +
    (this.peek()? " but found '"+this.peek().v+"'" : " but the query ended")); };

Parser.prototype.parse = function(){
  this.expectWord("SELECT");
  var sel = this.selectList();
  this.expectWord("FROM");
  var t = this.next();
  if(!t || t.t!=="word") throw new Error("Expected a table name after FROM");
  if(t.v.toLowerCase() !== "runs")
    throw new Error("The only table here is 'runs'. You asked for '" + t.v + "'.");
  var where = null, group = null, order = null, limit = null;
  if(this.eatWord("WHERE")) where = this.orExpr();
  if(this.eatWord("GROUP")){ this.expectWord("BY"); group = this.colName(); }
  if(this.eatWord("ORDER")){ this.expectWord("BY");
    var c = this.colName(); var dir = 1;
    if(this.eatWord("DESC")) dir = -1; else this.eatWord("ASC");
    order = {c:c, dir:dir}; }
  if(this.eatWord("LIMIT")){ var n = this.next();
    if(!n || n.t!=="num") throw new Error("LIMIT needs a number");
    limit = n.v; }
  if(this.i < this.k.length)
    throw new Error("Unexpected '" + this.k[this.i].v + "' after the end of the query");
  return {sel:sel, where:where, group:group, order:order, limit:limit};
};
Parser.prototype.colName = function(){
  var t = this.next();
  if(!t || t.t!=="word") throw new Error("Expected a column name");
  var c = t.v.toLowerCase();
  if(COLS.indexOf(c) < 0)
    throw new Error("No column '" + t.v + "'. Available: " + COLS.join(", "));
  return c;
};
Parser.prototype.selectList = function(){
  var out = [];
  do {
    var t = this.peek();
    if(t && t.t==="punc" && t.v==="*"){ this.i++; out.push({kind:"all"}); }
    else if(t && t.t==="word" && this.k[this.i+1] &&
            this.k[this.i+1].t==="punc" && this.k[this.i+1].v==="("){
      var fn = this.next().v.toUpperCase(); this.i++;      // consume '('
      var arg;
      var p = this.peek();
      if(p && p.t==="punc" && p.v==="*"){ this.i++; arg = "*"; }
      else arg = this.colName();
      var close = this.next();
      if(!close || close.v !== ")") throw new Error("Expected ) after " + fn + "(");
      if(["COUNT","AVG","SUM","MIN","MAX"].indexOf(fn) < 0)
        throw new Error("Unknown function " + fn + "(). Try COUNT, AVG, SUM, MIN or MAX.");
      out.push({kind:"agg", fn:fn, arg:arg});
    } else out.push({kind:"col", c:this.colName()});
  } while(this.eatPunc(","));
  return out;
};
Parser.prototype.eatPunc = function(p){ var t=this.peek();
  if(t && t.t==="punc" && t.v===p){ this.i++; return true; } return false; };

Parser.prototype.orExpr = function(){
  var l = this.andExpr();
  while(this.eatWord("OR")) l = {op:"OR", l:l, r:this.andExpr()};
  return l;
};
Parser.prototype.andExpr = function(){
  var l = this.cmp();
  while(this.eatWord("AND")) l = {op:"AND", l:l, r:this.cmp()};
  return l;
};
// A leading NOT negates whatever comparison follows, including `IS NULL`. Handling it
// as a prefix wrapper rather than a flag on each branch means it can never be parsed
// and then quietly dropped, which is what an earlier version did.
Parser.prototype.cmp = function(){
  if(this.eatPunc("(")){ var e = this.orExpr();
    if(!this.eatPunc(")")) throw new Error("Missing closing )"); return e; }
  if(this.eatWord("NOT")) return {op:"NOT", e:this.cmp()};
  return this.comparison();
};
Parser.prototype.comparison = function(){
  var c = this.colName();
  if(this.eatWord("IS")){
    var isNot = this.eatWord("NOT");
    this.expectWord("NULL");
    var n = {op:"null", c:c};
    return isNot ? {op:"NOT", e:n} : n;
  }
  var infixNot = this.eatWord("NOT");        // col NOT LIKE / col NOT IN
  if(this.eatWord("LIKE")){
    var lk = {op:"like", c:c, v:this.literal()};
    return infixNot ? {op:"NOT", e:lk} : lk;
  }
  if(this.eatWord("IN")){
    if(!this.eatPunc("(")) throw new Error("IN needs a ( list )");
    var vals = [];
    do { vals.push(this.literal()); } while(this.eatPunc(","));
    if(!this.eatPunc(")")) throw new Error("Missing ) after IN list");
    var inn = {op:"in", c:c, vals:vals};
    return infixNot ? {op:"NOT", e:inn} : inn;
  }
  if(infixNot) throw new Error("NOT after '" + c + "' must be followed by LIKE or IN");
  var t = this.next();
  if(!t || t.t!=="op") throw new Error("Expected a comparison after '" + c + "'");
  return {op:t.v, c:c, v:this.literal()};
};
Parser.prototype.literal = function(){
  var t = this.next();
  if(!t) throw new Error("Expected a value");
  if(t.t==="num") return t.v;
  if(t.t==="str") return t.v;
  if(t.t==="word"){
    var w = t.v.toLowerCase();
    if(w==="true") return true;
    if(w==="false") return false;
    if(w==="null") return null;
    return t.v;                       // bare word treated as a string
  }
  throw new Error("Expected a value but found '" + t.v + "'");
};

function truthy(node, row){
  switch(node.op){
    case "AND": return truthy(node.l,row) && truthy(node.r,row);
    case "OR":  return truthy(node.l,row) || truthy(node.r,row);
    case "NOT": return !truthy(node.e,row);
    case "null": return row[node.c] == null;
    case "like":{
      var pat = new RegExp("^" + String(node.v).replace(/[.*+?^${}()|[\]\\]/g,"\\$&")
                  .replace(/%/g,".*").replace(/_/g,".") + "$","i");
      return pat.test(String(row[node.c]==null?"":row[node.c]));
    }
    case "in": return node.vals.some(function(v){ return eq(row[node.c],v); });
    case "=":  return eq(row[node.c], node.v);
    case "!=": case "<>": return !eq(row[node.c], node.v);
    case ">":  return row[node.c] >  node.v;
    case "<":  return row[node.c] <  node.v;
    case ">=": return row[node.c] >= node.v;
    case "<=": return row[node.c] <= node.v;
  }
  return false;
}
function eq(a,b){
  if(typeof b === "boolean") return Boolean(a) === b;
  // SQLite stores booleans as 0/1, so `ok = 1` should match like `ok = true` does.
  if(typeof a === "boolean" && typeof b === "number") return Number(a) === b;
  if(typeof a === "string" && typeof b === "string") return a.toLowerCase()===b.toLowerCase();
  return a === b;
}

function aggregate(items, spec){
  var vals = items.map(function(r){ return spec.arg==="*" ? 1 : r[spec.arg]; })
                  .filter(function(x){ return x!=null; });
  switch(spec.fn){
    case "COUNT": return spec.arg==="*" ? items.length : vals.length;
    case "SUM":   return round(vals.reduce(function(a,b){return a+b;},0));
    case "AVG":   return vals.length? round(vals.reduce(function(a,b){return a+b;},0)/vals.length) : null;
    case "MIN":   return vals.length? vals.reduce(function(a,b){return a<b?a:b;}) : null;
    case "MAX":   return vals.length? vals.reduce(function(a,b){return a>b?a:b;}) : null;
  }
}
function round(x){ return typeof x === "number" ? Math.round(x*10000)/10000 : x; }
function label(s){ return s.kind==="all" ? "*"
  : s.kind==="col" ? s.c : s.fn.toLowerCase()+"("+s.arg+")"; }

export function runQuery(text, data){
  var ast = new Parser(tokenize(text)).parse();
  var rows = data || [];
  if(ast.where) rows = rows.filter(function(r){ return truthy(ast.where, r); });

  var hasAgg = ast.sel.some(function(s){ return s.kind==="agg"; });
  var cols, out;

  if(ast.group || hasAgg){
    var groups = new Map();
    if(ast.group){
      rows.forEach(function(r){
        var k = String(r[ast.group]);
        if(!groups.has(k)) groups.set(k, []);
        groups.get(k).push(r);
      });
    } else groups.set("__all__", rows);

    cols = ast.sel.map(label);
    out = [];
    groups.forEach(function(items, key){
      out.push(ast.sel.map(function(s){
        if(s.kind==="agg") return aggregate(items, s);
        if(s.kind==="col") return ast.group===s.c ? items[0][s.c] : items[0][s.c];
        return "*";
      }));
    });
  } else {
    var expand = ast.sel.some(function(s){ return s.kind==="all"; });
    cols = expand ? COLS : ast.sel.map(label);
    out = rows.map(function(r){ return cols.map(function(c){ return r[c]; }); });
  }

  if(ast.order){
    var idx = cols.indexOf(ast.order.c);
    if(idx < 0) throw new Error("ORDER BY '" + ast.order.c + "' is not in the SELECT list");
    out.sort(function(a,b){
      var x=a[idx], y=b[idx];
      if(x==null) x=-Infinity; if(y==null) y=-Infinity;
      return (x<y?-1:x>y?1:0) * ast.order.dir;
    });
  }
  var total = out.length;
  if(ast.limit != null) out = out.slice(0, ast.limit);
  return {cols:cols, rows:out, total:total};
}
