// Hồi quy qua giao diện mở trợ lý: đúng danh tính và không ghi đè trang đã rời.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(process.argv[2] || path.join(__dirname,'ho-tro.js'),'utf8');
const crm = {id:'bdsg_crm',name:'BDSG CRM',url:'https://crm.bdsg.vn/',purpose:'Quan hệ khách hàng'};
const shop = {id:'bdsg_shop',name:'BDSG SHOP',url:'https://bdsgshop.bdsg.vn/',purpose:'Thương mại điện tử'};
function profile(product) {
  const id='tro-ly-'+product.id, brain_id='brain-'+product.id+'-v1';
  return {id,brain_id,platform_id:product.id,name:'Trợ lý '+product.name,description:product.purpose,platform:product,
    brain:{id,brain_id,platform_id:product.id,mission:'Nhiệm vụ kiểm thử',starter:'Câu hỏi kiểm thử',version:1,knowledge:{facts:[product.purpose]},system_instructions:'Chỉ hướng dẫn trong phạm vi'}};
}
function environment(api) {
  const nodes={'#customer-log':{innerHTML:''},'#assistant-clear':{disabled:false}};
  const context={window:{},main:{innerHTML:''},location:{hash:'#support/tro-ly-bdsg_crm'},state:{products:[crm,shop]},api,
    document:{addEventListener(){}},$:selector=>nodes[selector],esc:String,icon:()=>'',clean:String};
  vm.runInNewContext(source,context);
  return context;
}
(async()=>{
  const valid=environment(async()=>profile(crm));
  await valid.window.BDSGSupport.open('tro-ly-bdsg_crm');
  assert.ok(valid.main.innerHTML.includes('id="customer-support-form"'),'Hồ sơ hợp lệ phải mở được hội thoại');
  const wrong=environment(async()=>profile(shop));
  await wrong.window.BDSGSupport.open('tro-ly-bdsg_crm');
  assert.ok(!wrong.main.innerHTML.includes('id="customer-support-form"'),'Không mở hồ sơ Shop tại đường CRM');
  assert.ok(wrong.main.innerHTML.includes('không đúng trợ lý'),'Phải giải thích khi phản hồi sai danh tính');
  let release;
  const late=environment(()=>new Promise(resolve=>{release=resolve;}));
  const opening=late.window.BDSGSupport.open('tro-ly-bdsg_crm');
  late.location.hash='#support/foo/bar';late.main.innerHTML='Trang giao việc';
  release(profile(crm));await opening;
  assert.equal(late.main.innerHTML,'Trang giao việc','Hồ sơ đến muộn không ghi đè đường không hợp lệ');
  console.log('PASS: valid assistant, wrong identity rejection and late-response route isolation');
})().catch(error=>{console.error(error.message);process.exitCode=1;});
