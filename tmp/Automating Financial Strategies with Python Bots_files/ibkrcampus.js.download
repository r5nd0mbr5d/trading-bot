
async function shareWithIBKR(){
 const qs = window.location.search;
 if (qs){
   let ibban = null; 
   let src = null; 
   let words = null;
   let kwords = null; 
   let campaign = null; 
   let page = encodeURI(window.location.pathname);
   let ibkr_web = getIBKRCookie();

   if (typeof URLSearchParams === 'function'){ 
       const params = new URLSearchParams(qs);
       ibban = params.get('ibban'); 
       src = params.get('src');
       words = params.get('w');
       campaign = params.get('c');
       kwords = params.get('kw'); 
   }
   else { // "old way"
       let match = qs.match(/(\?|\&)src=([^\?|\&]+)/);
       src = `${match[2]}`;
  
       match = qs.match(/(\?|\&)w=([^\?|\&]+)/);
       ban = `${match[2]}`;
 
       match = qs.match(/(\?|\&)w=([^\?|\&]+)/);
       words = `${match[2]}`;

       match = qs.match(/(\?|\&)c=([^\?|\&]+)/);
       campaign = `${match[2]}`;
    
       match = qs.match(/(\?|\&)kw=([^\?|\&]+)/);
       kwords = `${match[2]}`;
    }

   if (ibban && src){
      let ibkr_web = getIBKRCookie(); 
      let url = 'https://www.interactivebrokers.com/mkt/ibkrmktrk.php?src='+src+'&ibs=campus&ibkrweb='+ibkr_web+'&cmp='+campaign+'&words='+words+'&keywords='+kwords+'&page='+page;
      console.log(" URL: "+url); 
      console.log(" Cookie? " + ibkr_web);
      const response = await fetch(url, {
	      method: "GET",
              mode: "cors",
              cache: "no-cache",
              credentials: "include",
              referrerPolicy: "origin-when-cross-origin",
            });
      const jsonData= await response.json();
      if (jsonData['ibkrweb']){
          setIBKRCookie('ibkrweb',jsonData['ibkrweb']);
      }
   }
 }
}

function setIBKRCookie(cn,cv){ 
  if (cn == null){ return; } 
  console.log(cn+"|"+cv);
  let e = new Date(); e.setMilliseconds(e.getMilliseconds() + (360 * 864e+5)); 
  document.cookie = cn+'='+encodeURIComponent(cv)+';expires='+e.toGMTString()+';path=/;domain='+location.hostname.replace(/.+(\.\w*b\w*\.\w*.{0,4})/, "$1")+';secure;SameSite=None';
}

function getIBKRCookie(cn){ 
  let r; 
  let d = (r = new RegExp("(?:^|; )ibkrweb=([^;]*)").exec(document.cookie)) ? decodeURIComponent(r[1]) : null;
  console.log(" Get IBC:"+d); 
  if (d == null){
      d = (r = new RegExp("(?:^|; )web=([^;]*)").exec(document.cookie)) ? decodeURIComponent(r[1]) : null;
      console.log("Get IBC:"+d);
  } 
  return d;
}

shareWithIBKR();

