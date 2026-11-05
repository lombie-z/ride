import { Box3, BufferGeometry, CanvasTexture, Float32BufferAttribute, Mesh, type MeshStandardMaterial, type Object3D, Vector3 } from 'three';

// The throttle pill's symbol, swapped by what a press does (components/three/ride.tsx): play, or pause while riding. The
// bikes' glbs model chevrons in its place: each bike's are hidden and its glyph material put on a plate over the pill.

function symbol(draw: (g: CanvasRenderingContext2D) => void) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const g = canvas.getContext('2d') as CanvasRenderingContext2D;
  g.fillStyle = '#000';
  g.fillRect(0, 0, 128, 128);
  g.fillStyle = '#fff';
  draw(g);
  return new CanvasTexture(canvas);
}

let glyphs: { play: CanvasTexture; pause: CanvasTexture } | null = null;
export function pillGlyphs() {
  glyphs ??= {
    play: symbol((g) => {
      g.beginPath();
      g.moveTo(34, 112);
      g.lineTo(34, 16);
      g.lineTo(108, 64);
      g.closePath();
      g.fill();
    }),
    pause: symbol((g) => {
      g.fillRect(28, 18, 26, 92);
      g.fillRect(74, 18, 26, 92);
    }),
  };
  return glyphs;
}

/** Puts `material` (the bike's glyph material) on a plate over its pill, at its ButtonCentre: the modelled glyphs hidden. */
export function pillPlate(scene: Object3D, material: MeshStandardMaterial, pill?: MeshStandardMaterial) {
  const centre = scene.getObjectByName('ButtonCentre');
  if (!centre?.parent) return null;
  scene.updateMatrixWorld(true);
  const box = new Box3();
  const hidden: Object3D[] = [];
  const corner = new Vector3();
  const toCentre = centre.matrixWorld.clone().invert();
  scene.traverse((o) => {
    const m = o as Mesh;
    if (!m.isMesh || m.material !== material) return;
    hidden.push(m);
    const p = m.geometry.attributes.position;
    for (let i = 0; i < p.count; i++) box.expandByPoint(corner.fromBufferAttribute(p, i).applyMatrix4(m.matrixWorld).applyMatrix4(toCentre));
  });
  for (const o of hidden) o.visible = false;
  const y = (hidden.length ? box.max.y : 0.012) + 0.0015;
  // (Up the tank is +x, the rider's right +z: the rider's looking along +x. Long along the tank: it's foreshortened.)
  const hw = 0.042;
  const hl = 0.066;
  const geometry = new BufferGeometry();
  geometry.setAttribute('position', new Float32BufferAttribute([-hl, y, -hw, -hl, y, hw, hl, y, hw, hl, y, -hw], 3));
  // (Seen from the seat: u to the rider's right, v away up the tank.)
  geometry.setAttribute('uv', new Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 1], 2));
  geometry.setIndex([0, 1, 2, 0, 2, 3]);
  geometry.computeVertexNormals();
  const plate = new Mesh(geometry, material);
  plate.name = 'PillSymbol';
  plate.position.copy(centre.position);
  plate.quaternion.copy(centre.quaternion);
  plate.scale.copy(centre.scale);
  plate.renderOrder = 3;
  centre.parent.add(plate);
  material.transparent = true;
  // (Drawn once. Two-sided and see-through it would be drawn back then front, which makes three look up its program each time.)
  material.forceSinglePass = true;
  material.depthWrite = false;
  material.color.setRGB(0, 0, 0);
  // (The pill itself goes dark glass under it, for the symbol to stand out.)
  pill?.color.setRGB(0.05, 0.05, 0.06);
  const { play } = pillGlyphs();
  material.emissiveMap = play;
  material.alphaMap = play;
  return () => {
    plate.removeFromParent();
    geometry.dispose();
    for (const o of hidden) o.visible = true;
  };
}
