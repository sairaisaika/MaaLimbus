import test from 'node:test';
import assert from 'node:assert/strict';
import {SINNERS,toggleSinner,moveSinner,completeOrder} from './teamOrder.ts';
test('clicks construct requested team2 deployment without duplicates',()=>{
 let order=[];for(const n of [3,4,9,1,7,2,12,5,8,10,11,6])order=toggleSinner(order,SINNERS[n-1]);
 assert.ok(completeOrder(order));assert.equal(order.at(-1),'Hong Lu');
 order=toggleSinner(order,'Faust');assert.equal(order.length,11);assert.ok(!completeOrder(order));
});
test('reorder is immutable and incomplete/duplicate/unknown cannot save',()=>{
 const original=[...SINNERS], moved=moveSinner(original,5,1);
 assert.equal(original[5],'Hong Lu');assert.equal(moved[6],'Hong Lu');
 assert.ok(!completeOrder([...SINNERS.slice(1),'Faust']));
 assert.throws(()=>toggleSinner([], 'unknown'));assert.deepEqual(moveSinner(original,0,-1),original);
});
