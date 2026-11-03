/* One owner for a screen's context and disposable presentation resources. */
(function(root,factory){
  if(typeof module==='object'&&module.exports)module.exports=factory();
  else root.ScholionViewLifecycle=factory();
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  function create(services){
    const timers=services.timers||globalThis;
    let active=null,serial=0;
    const snapshot=()=>Object.freeze({...services.context()});
    const matches=stamp=>JSON.stringify(stamp)===JSON.stringify(snapshot());
    const owns=(scope,node)=>!!scope&&!scope.closed&&scope.root.isConnected&&
      (scope.root===node||scope.root.contains(node));
    function dispose(){
      const old=active;if(!old)return;
      active=null;old.closed=true;
      for(const cleanup of [...old.cleanups])cleanup();
      old.cleanups.clear();
      if(services.dispose)services.dispose(old.root);
    }
    function begin(old,key){
      dispose();
      const root=old.cloneNode(false);old.replaceWith(root);
      active={root,key,serial:++serial,context:snapshot(),closed:false,cleanups:new Set()};
      return root;
    }
    function own(node,cleanup){
      const scope=active;let retained=true;
      const release=()=>{if(!retained)return;retained=false;scope?.cleanups.delete(release);cleanup();};
      if(owns(scope,node))scope.cleanups.add(release);else release();
      return release;
    }
    function schedule(node,callback,delay,repeated){
      const scope=active;
      if(!owns(scope,node))return ()=>{};
      let release=()=>{};
      const tick=()=>{if(!owns(scope,node)){release();return;}if(!repeated)release();callback();};
      const id=repeated?timers.setInterval(tick,delay):timers.setTimeout(tick,delay);
      release=own(node,()=>repeated?timers.clearInterval(id):timers.clearTimeout(id));
      return release;
    }
    return Object.freeze({
      begin,dispose,snapshot,matches,own,
      current:node=>owns(active,node),
      recontext:node=>{if(owns(active,node))active.context=snapshot();},
      context:node=>owns(active,node)?active.context:null,
      interval:(node,fn,ms)=>schedule(node,fn,ms,true),
      timeout:(node,fn,ms)=>schedule(node,fn,ms,false),
      status:()=>active?{serial:active.serial,key:active.key,context:active.context,resources:active.cleanups.size}:null
    });
  }
  return Object.freeze({create});
});
