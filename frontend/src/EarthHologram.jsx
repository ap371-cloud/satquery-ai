import React, { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'

const EARTH_TEX = 'https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg'
const EARTH_DARK = 'https://unpkg.com/three-globe/example/img/earth-dark.jpg'
const EARTH_CLOUD = 'https://unpkg.com/three-globe/example/img/earth-water.png'

function mulberry32(a) {
  return function () {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function makeProceduralEarth() {
  const c = document.createElement('canvas')
  c.width = 1024
  c.height = 512
  const ctx = c.getContext('2d')
  ctx.fillStyle = '#123c63'
  ctx.fillRect(0, 0, 1024, 512)
  const land = ['#2d6a4f', '#358058', '#3c7a4a', '#55804b', '#718a4e']
  const rand = mulberry32(42)
  const blobs = []
  for (let i = 0; i < 210; i++) {
    const x = rand() * 1024
    const y = rand() * 512
    const rx = 12 + rand() * 55
    const ry = 6 + rand() * 30
    if ((x - 500) * (x - 500) + (y - 256) * (y - 256) < 400 * 400) blobs.push({ x, y, rx, ry, color: land[Math.floor(rand() * land.length)] })
  }
  blobs.sort((a, b) => b.rx * b.ry - a.rx * a.ry)
  for (const b of blobs) {
    if (rand() < 0.3) continue
    ctx.fillStyle = b.color
    ctx.globalAlpha = 0.85 + rand() * 0.15
    ctx.beginPath()
    ctx.ellipse(b.x, b.y, b.rx, b.ry, rand() * Math.PI, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.globalAlpha = 1
  for (let i = 0; i < 900; i++) {
    const x = rand() * 1024
    const y = rand() * 512
    ctx.fillStyle = i % 3 === 0 ? '#8fb9d9' : '#60a6c9'
    ctx.globalAlpha = 0.5
    ctx.fillRect(x, y, 1.5 + rand() * 2, 1)
  }
  ctx.globalAlpha = 1
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  return t
}

export default function EarthHologram() {
  const containerRef = useRef(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const scene = new THREE.Scene()
    const width = container.clientWidth
    const height = container.clientHeight
    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100)
    camera.position.set(0, 0.35, 5.2)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    container.appendChild(renderer.domElement)

    const group = new THREE.Group()
    scene.add(group)
    group.position.set(width > 1100 ? 1.85 : 0, width > 1100 ? 0.2 : 0, 0)
    group.rotation.z = THREE.MathUtils.degToRad(16)
    group.rotation.y = 0.5

    const procedural = makeProceduralEarth()
    const dayMat = new THREE.MeshPhongMaterial({
      color: 0xffffff,
      map: procedural,
      shininess: 22,
      specular: new THREE.Color(0x334155),
      transparent: true,
      opacity: 0.92,
    })
    const earth = new THREE.Mesh(new THREE.SphereGeometry(1.7, 96, 96), dayMat)
    earth.rotation.z = THREE.MathUtils.degToRad(-12)
    group.add(earth)

    const texLoader = new THREE.TextureLoader()
    texLoader.setCrossOrigin('anonymous')
    texLoader.load(EARTH_TEX, (t) => {
      dayMat.map = t
      dayMat.color.set(0xffffff)
      dayMat.needsUpdate = true
      setLoaded(true)
    }, undefined, () => { setLoaded(true) })
    texLoader.load(EARTH_DARK, (t) => {
      if (dayMat.map && dayMat.map !== procedural) return
      dayMat.map = t
      dayMat.needsUpdate = true
    }, undefined, () => {})

    const cloudMat = new THREE.MeshPhongMaterial({
      transparent: true,
      opacity: 0.32,
      depthWrite: false,
    })
    texLoader.load(EARTH_CLOUD, (t) => {
      cloudMat.map = t
      cloudMat.transparent = true
      cloudMat.opacity = 0.3
      cloudMat.needsUpdate = true
    })
    const clouds = new THREE.Mesh(new THREE.SphereGeometry(1.72, 96, 96), cloudMat)
    group.add(clouds)

    const glowMat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      side: THREE.BackSide,
      uniforms: { c: { value: new THREE.Color(0x4f8df0) } },
      vertexShader: `varying vec3 vN; void main(){ vN = normalize(normalMatrix * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
      fragmentShader: `varying vec3 vN; uniform vec3 c; void main(){ float i = pow(0.62 - dot(vN, vec3(0,0,1.0)), 2.2); gl_FragColor = vec4(c, i * 0.85); }`,
      blending: THREE.AdditiveBlending,
    })
    const glow = new THREE.Mesh(new THREE.SphereGeometry(2.35, 64, 64), glowMat)
    group.add(glow)

    const gridMat = new THREE.MeshBasicMaterial({
      color: 0x7fb0ff,
      wireframe: true,
      transparent: true,
      opacity: 0.06,
      depthWrite: false,
    })
    const grid = new THREE.Mesh(new THREE.SphereGeometry(1.735, 48, 30), gridMat)
    group.add(grid)

    const ringGeo = new THREE.RingGeometry(2.15, 2.55, 128)
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x4f8df0,
      transparent: true,
      opacity: 0.18,
      side: THREE.DoubleSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    const ring = new THREE.Mesh(ringGeo, ringMat)
    ring.position.set(-0.2, 0.1, 0)
    ring.rotation.x = THREE.MathUtils.degToRad(65)
    ring.rotation.z = THREE.MathUtils.degToRad(-8)
    group.add(ring)

    const starsGeo = new THREE.BufferGeometry()
    const N = 900
    const pos = new Float32Array(N * 3)
    for (let i = 0; i < N; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 90
      pos[i * 3 + 1] = (Math.random() - 0.5) * 60
      pos[i * 3 + 2] = (Math.random() - 0.5) * 60 - 10
    }
    starsGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    const starsMat = new THREE.PointsMaterial({ color: 0xcfe0ff, size: 0.12, transparent: true, opacity: 0.55, sizeAttenuation: true })
    const stars = new THREE.Points(starsGeo, starsMat)
    scene.add(stars)

    const lights = [
      new THREE.AmbientLight(0xffffff, 1.15),
      new THREE.DirectionalLight(0x9ad4ff, 1.4),
      new THREE.PointLight(0x4f8df0, 0.5),
    ]
    lights[1].position.set(3, 2, 4)
    lights.forEach(l => scene.add(l))

    let raf = 0
    const animate = () => {
      raf = requestAnimationFrame(animate)
      earth.rotation.y += 0.0012
      clouds.rotation.y += 0.0015
      group.rotation.y = Math.sin(Date.now() * 0.00012) * 0.05 + Math.sin(Date.now() * 0.000047) * 0.15
      ring.rotation.z += 0.0006
      stars.rotation.y += 0.00008
      const bob = Math.sin(Date.now() * 0.0006) * 0.06
      group.position.y = bob + (width > 1100 ? 0.2 : 0)
      renderer.render(scene, camera)
    }
    animate()

    const onResize = () => {
      const w = container.clientWidth
      const h = container.clientHeight
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
      group.position.x = w > 1100 ? 1.85 : 0
      group.position.y = w > 1100 ? 0.2 : 0
    }
    window.addEventListener('resize', onResize)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      renderer.dispose()
      container.removeChild(renderer.domElement)
    }
  }, [])

  return (
    <div ref={containerRef} className={`earth-hologram${loaded ? ' is-loaded' : ''}`} aria-hidden="true" />
  )
}