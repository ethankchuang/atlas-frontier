'use client';

import React, { Suspense, useRef, useEffect, useState, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { useGLTF, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader.js';
import JSZip from 'jszip';

interface Room3DViewerProps {
    modelUrl: string;
    onLoadError?: () => void;
    onLoadSuccess?: () => void;
}

interface ModelProps {
    url: string;
    onError?: () => void;
    onSuccess?: () => void;
}

interface LayeredSceneData {
    meshLayers: { name: string; geometry: THREE.BufferGeometry }[];
}

// View angle indicator that shows current look direction
// Appears in center, fades out 2 seconds after user stops moving
function ViewAngleIndicator({ angleRef }: { angleRef: React.MutableRefObject<number> }) {
    const [angle, setAngle] = useState(0);
    const [visible, setVisible] = useState(false);
    const lastAngleRef = useRef(0);
    const hideTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        const interval = setInterval(() => {
            const currentAngle = angleRef.current;
            setAngle(currentAngle);

            // Check if angle changed (user is moving)
            if (Math.abs(currentAngle - lastAngleRef.current) > 0.001) {
                setVisible(true);
                lastAngleRef.current = currentAngle;

                // Clear existing timeout and set new one
                if (hideTimeoutRef.current) {
                    clearTimeout(hideTimeoutRef.current);
                }
                hideTimeoutRef.current = setTimeout(() => {
                    setVisible(false);
                }, 2000);
            }
        }, 50);

        return () => {
            clearInterval(interval);
            if (hideTimeoutRef.current) {
                clearTimeout(hideTimeoutRef.current);
            }
        };
    }, [angleRef]);

    // Negate angle: euler.y is negative when looking right, but SVG rotation is positive clockwise
    const angleDeg = -(angle * 180) / Math.PI;

    return (
        <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 pointer-events-none transition-opacity duration-300 ${visible ? 'opacity-100' : 'opacity-0'}`}>
            <div className="bg-black/40 backdrop-blur-sm rounded-full p-2">
                <svg width="48" height="48" viewBox="0 0 48 48">
                    {/* Background circle */}
                    <circle cx="24" cy="24" r="22" fill="none" stroke="white" strokeOpacity="0.15" strokeWidth="1" />

                    {/* View direction cone/fan */}
                    <g transform={`rotate(${angleDeg}, 24, 24)`}>
                        {/* Fan shape showing ~60° FOV */}
                        <path
                            d="M 24 24 L 10 6 A 22 22 0 0 1 38 6 Z"
                            fill="white"
                            fillOpacity="0.25"
                        />
                        {/* Center direction line */}
                        <line x1="24" y1="24" x2="24" y2="4" stroke="white" strokeOpacity="0.5" strokeWidth="1.5" />
                    </g>

                    {/* Center dot */}
                    <circle cx="24" cy="24" r="2" fill="white" fillOpacity="0.4" />
                </svg>
            </div>
        </div>
    );
}

// FPS-style camera controls matching the official Hunyuan viewer
// - Mouse drag to look around (rotation)
// - WASD keys to move (constrained to 0.3 units from origin)
function FPSControls({ onAngleChange }: { onAngleChange?: (angle: number) => void }) {
    const { camera, gl } = useThree();
    const isPointerDown = useRef(false);
    const previousPointer = useRef({ x: 0, y: 0 });
    const euler = useRef(new THREE.Euler(0, 0, 0, 'YXZ'));
    const keys = useRef({ w: false, a: false, s: false, d: false });

    const MOVE_SPEED = 0.01;
    const MAX_DISTANCE = 0.3; // Max distance from origin (matches official viewer)
    const ROTATION_SPEED = 0.003;

    useEffect(() => {
        // Initialize camera looking forward (negative Z)
        camera.position.set(0, 0, 0);
        euler.current.setFromQuaternion(camera.quaternion);

        const domElement = gl.domElement;

        const onPointerDown = (e: PointerEvent) => {
            isPointerDown.current = true;
            previousPointer.current = { x: e.clientX, y: e.clientY };
            domElement.style.cursor = 'grabbing';
        };

        const onPointerUp = () => {
            isPointerDown.current = false;
            domElement.style.cursor = 'grab';
        };

        const onPointerMove = (e: PointerEvent) => {
            if (!isPointerDown.current) return;

            const deltaX = e.clientX - previousPointer.current.x;
            const deltaY = e.clientY - previousPointer.current.y;
            previousPointer.current = { x: e.clientX, y: e.clientY };

            // Rotate camera based on mouse movement
            euler.current.y -= deltaX * ROTATION_SPEED;
            euler.current.x -= deltaY * ROTATION_SPEED;

            // Clamp vertical rotation to avoid flipping
            euler.current.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, euler.current.x));
            // Clamp horizontal rotation to 180° view (±90° from center)
            euler.current.y = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, euler.current.y));

            camera.quaternion.setFromEuler(euler.current);
            onAngleChange?.(euler.current.y);
        };

        const onPointerLeave = () => {
            isPointerDown.current = false;
            domElement.style.cursor = 'grab';
        };

        const isInputFocused = () => {
            const active = document.activeElement;
            if (!active) return false;
            const tag = active.tagName.toLowerCase();
            return tag === 'input' || tag === 'textarea' || (active as HTMLElement).isContentEditable;
        };

        const onKeyDown = (e: KeyboardEvent) => {
            if (isInputFocused()) return; // Don't capture WASD when typing in chat
            const key = e.key.toLowerCase();
            if (key in keys.current) {
                keys.current[key as keyof typeof keys.current] = true;
            }
        };

        const onKeyUp = (e: KeyboardEvent) => {
            const key = e.key.toLowerCase();
            if (key in keys.current) {
                keys.current[key as keyof typeof keys.current] = false;
            }
        };

        // Touch support for mobile
        const onTouchStart = (e: TouchEvent) => {
            if (e.touches.length === 1) {
                isPointerDown.current = true;
                previousPointer.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            }
        };

        const onTouchEnd = () => {
            isPointerDown.current = false;
        };

        const onTouchMove = (e: TouchEvent) => {
            if (!isPointerDown.current || e.touches.length !== 1) return;

            const touch = e.touches[0];
            const deltaX = touch.clientX - previousPointer.current.x;
            const deltaY = touch.clientY - previousPointer.current.y;
            previousPointer.current = { x: touch.clientX, y: touch.clientY };

            euler.current.y -= deltaX * ROTATION_SPEED;
            euler.current.x -= deltaY * ROTATION_SPEED;
            euler.current.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, euler.current.x));
            euler.current.y = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, euler.current.y));

            camera.quaternion.setFromEuler(euler.current);
            onAngleChange?.(euler.current.y);
        };

        domElement.style.cursor = 'grab';
        domElement.addEventListener('pointerdown', onPointerDown);
        domElement.addEventListener('pointerup', onPointerUp);
        domElement.addEventListener('pointermove', onPointerMove);
        domElement.addEventListener('pointerleave', onPointerLeave);
        domElement.addEventListener('touchstart', onTouchStart, { passive: true });
        domElement.addEventListener('touchend', onTouchEnd);
        domElement.addEventListener('touchmove', onTouchMove, { passive: true });
        window.addEventListener('keydown', onKeyDown);
        window.addEventListener('keyup', onKeyUp);

        return () => {
            domElement.removeEventListener('pointerdown', onPointerDown);
            domElement.removeEventListener('pointerup', onPointerUp);
            domElement.removeEventListener('pointermove', onPointerMove);
            domElement.removeEventListener('pointerleave', onPointerLeave);
            domElement.removeEventListener('touchstart', onTouchStart);
            domElement.removeEventListener('touchend', onTouchEnd);
            domElement.removeEventListener('touchmove', onTouchMove);
            window.removeEventListener('keydown', onKeyDown);
            window.removeEventListener('keyup', onKeyUp);
        };
    }, [camera, gl]);

    // Handle WASD movement each frame
    useFrame(() => {
        const { w, a, s, d } = keys.current;
        if (!w && !a && !s && !d) return;

        // Get forward and right vectors from camera orientation
        const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
        const right = new THREE.Vector3(1, 0, 0).applyQuaternion(camera.quaternion);

        // Keep movement horizontal (no flying up/down)
        forward.y = 0;
        forward.normalize();
        right.y = 0;
        right.normalize();

        const movement = new THREE.Vector3();
        if (w) movement.add(forward);
        if (s) movement.sub(forward);
        if (d) movement.add(right);
        if (a) movement.sub(right);

        if (movement.length() > 0) {
            movement.normalize().multiplyScalar(MOVE_SPEED);

            // Calculate new position
            const newPos = camera.position.clone().add(movement);

            // Constrain to MAX_DISTANCE from origin (horizontal plane only)
            const horizontalDist = Math.sqrt(newPos.x * newPos.x + newPos.z * newPos.z);
            if (horizontalDist <= MAX_DISTANCE) {
                camera.position.copy(newPos);
            } else {
                // Clamp to max distance
                const scale = MAX_DISTANCE / horizontalDist;
                newPos.x *= scale;
                newPos.z *= scale;
                camera.position.copy(newPos);
            }
        }
    });

    return null;
}

// Detect file type from URL (no logging - called frequently during render)
function getFileType(url: string): 'glb' | 'ply' | 'zip' | 'unknown' {
    const cleanUrl = url.split('?')[0].toLowerCase();
    if (cleanUrl.endsWith('.glb') || cleanUrl.endsWith('.gltf')) return 'glb';
    if (cleanUrl.endsWith('.ply')) return 'ply';
    if (cleanUrl.endsWith('.zip')) return 'zip';
    return 'unknown';
}

// Load and parse a PLY file from ArrayBuffer
async function loadPLYFromBuffer(buffer: ArrayBuffer): Promise<THREE.BufferGeometry> {
    return new Promise((resolve, reject) => {
        try {
            const loader = new PLYLoader();
            const geometry = loader.parse(buffer);
            geometry.computeVertexNormals();
            resolve(geometry);
        } catch (error) {
            reject(error);
        }
    });
}

// Extract and load PLY meshes from a hunyuan_world ZIP
// Note: HunyuanWorld PLY files have vertex colors baked in, no need for separate textures
async function loadHunyuanWorldZip(url: string): Promise<LayeredSceneData> {
    console.log('[Room3DViewer] Starting ZIP download...', { url: url.slice(0, 80) });
    const startTime = performance.now();

    const response = await fetch(url);
    if (!response.ok) {
        console.error('[Room3DViewer] ZIP fetch failed:', { status: response.status, statusText: response.statusText });
        throw new Error(`Failed to fetch ZIP: ${response.status}`);
    }

    const arrayBuffer = await response.arrayBuffer();
    const downloadTime = ((performance.now() - startTime) / 1000).toFixed(2);
    console.log('[Room3DViewer] ZIP downloaded:', {
        sizeKB: (arrayBuffer.byteLength / 1024).toFixed(1),
        sizeMB: (arrayBuffer.byteLength / (1024 * 1024)).toFixed(2),
        downloadTimeSeconds: downloadTime
    });

    console.log('[Room3DViewer] Extracting ZIP...');
    const zip = await JSZip.loadAsync(arrayBuffer);
    const allFiles = Object.keys(zip.files);
    console.log('[Room3DViewer] ZIP contents:', { totalFiles: allFiles.length, files: allFiles });

    const meshLayers: { name: string; geometry: THREE.BufferGeometry }[] = [];

    // Load mesh layers (mesh_layer0.ply, mesh_layer1.ply, mesh_layer2.ply)
    const plyFiles = Object.keys(zip.files).filter(f => f.endsWith('.ply')).sort();
    for (const plyName of plyFiles) {
        try {
            const plyData = await zip.files[plyName].async('arraybuffer');
            const geometry = await loadPLYFromBuffer(plyData);
            meshLayers.push({ name: plyName, geometry });
            console.log(`[Room3DViewer] Loaded mesh: ${plyName}, hasColors: ${geometry.hasAttribute('color')}`);
        } catch (error) {
            console.warn(`[Room3DViewer] Failed to load ${plyName}:`, error);
        }
    }

    const totalTime = ((performance.now() - startTime) / 1000).toFixed(2);
    console.log('[Room3DViewer] ZIP extraction complete:', {
        meshLayersLoaded: meshLayers.length,
        meshNames: meshLayers.map(m => m.name),
        totalTimeSeconds: totalTime
    });

    return { meshLayers };
}

// Component to render the layered hunyuan_world scene
function HunyuanWorldScene({ data, onSuccess }: { data: LayeredSceneData; onSuccess?: () => void }) {
    const groupRef = useRef<THREE.Group>(null);
    const [isSetup, setIsSetup] = useState(false);
    const onSuccessRef = useRef(onSuccess);

    useEffect(() => {
        onSuccessRef.current = onSuccess;
    }, [onSuccess]);

    useEffect(() => {
        if (!groupRef.current || isSetup) return;

        const group = groupRef.current;

        // Clear existing children
        while (group.children.length > 0) {
            group.remove(group.children[0]);
        }

        // Create meshes for each layer
        // HunyuanWorld PLY files have vertex colors baked in - use MeshBasicMaterial
        // NO centering or scaling - user is inside the scene looking out
        data.meshLayers.forEach((layer) => {
            const material = new THREE.MeshBasicMaterial({
                vertexColors: true,
                side: THREE.DoubleSide,
            });

            const mesh = new THREE.Mesh(layer.geometry, material);
            mesh.name = layer.name;

            // Apply rotations to match HunyuanWorld coordinate system
            mesh.rotateX(-Math.PI / 2);
            mesh.rotateZ(-Math.PI / 2);

            group.add(mesh);
        });

        console.log('[Room3DViewer] Scene setup complete:', {
            meshLayers: data.meshLayers.length,
            hasVertexColors: data.meshLayers.map(l => l.geometry.hasAttribute('color'))
        });

        setIsSetup(true);
        onSuccessRef.current?.();
    }, [data, isSetup]);

    return <group ref={groupRef} />;
}

// ZIP Model loader component (for hunyuan_world output)
function ZIPModel({ url, onError, onSuccess }: ModelProps) {
    const [sceneData, setSceneData] = useState<LayeredSceneData | null>(null);
    const [hasError, setHasError] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const onErrorRef = useRef(onError);
    const onSuccessRef = useRef(onSuccess);

    // Keep refs updated
    useEffect(() => {
        onErrorRef.current = onError;
        onSuccessRef.current = onSuccess;
    }, [onError, onSuccess]);

    useEffect(() => {
        let cancelled = false;
        setIsLoading(true);
        setHasError(false);
        setSceneData(null);

        loadHunyuanWorldZip(url)
            .then((data) => {
                if (cancelled) return;
                if (data.meshLayers.length === 0) {
                    throw new Error('No mesh layers found in ZIP');
                }
                setSceneData(data);
                setIsLoading(false);
            })
            .catch((error) => {
                if (cancelled) return;
                console.error('[Room3DViewer] Failed to load ZIP:', error);
                setHasError(true);
                setIsLoading(false);
                onErrorRef.current?.();
            });

        return () => { cancelled = true; };
    }, [url]); // Only depend on url, use refs for callbacks

    if (hasError) return null;
    if (isLoading || !sceneData) return null;

    return <HunyuanWorldScene data={sceneData} onSuccess={onSuccessRef.current} />;
}

// PLY Model loader component
function PLYModel({ url, onError, onSuccess }: ModelProps) {
    const groupRef = useRef<THREE.Group>(null);
    const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null);
    const [hasError, setHasError] = useState(false);
    const onErrorRef = useRef(onError);
    const onSuccessRef = useRef(onSuccess);

    // Keep refs updated
    useEffect(() => {
        onErrorRef.current = onError;
        onSuccessRef.current = onSuccess;
    }, [onError, onSuccess]);

    useEffect(() => {
        const loader = new PLYLoader();
        loader.load(
            url,
            (loadedGeometry) => {
                loadedGeometry.computeVertexNormals();
                setGeometry(loadedGeometry);
                onSuccessRef.current?.();
            },
            undefined,
            (error) => {
                console.error('[Room3DViewer] Failed to load PLY:', error);
                setHasError(true);
                onErrorRef.current?.();
            }
        );
    }, [url]); // Only depend on url

    useEffect(() => {
        if (geometry && groupRef.current) {
            // Clear existing children
            while (groupRef.current.children.length > 0) {
                groupRef.current.remove(groupRef.current.children[0]);
            }

            // Create mesh with the geometry
            const material = new THREE.MeshStandardMaterial({
                vertexColors: geometry.hasAttribute('color'),
                side: THREE.DoubleSide,
            });
            const mesh = new THREE.Mesh(geometry, material);

            // Compute bounding box to center and scale
            const box = new THREE.Box3().setFromObject(mesh);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());

            mesh.position.sub(center);

            const maxDim = Math.max(size.x, size.y, size.z);
            if (maxDim > 0) {
                const scale = 5 / maxDim;
                mesh.scale.setScalar(scale);
            }

            groupRef.current.add(mesh);
        }
    }, [geometry]);

    if (hasError) return null;
    return <group ref={groupRef} />;
}

// GLB/GLTF Model loader component
function GLBModel({ url, onError, onSuccess }: ModelProps) {
    const groupRef = useRef<THREE.Group>(null);
    const [hasError, setHasError] = useState(false);

    // Load the GLB model
    const { scene } = useGLTF(url, true, undefined, (error) => {
        console.error('[Room3DViewer] Failed to load GLB:', error);
        setHasError(true);
        onError?.();
    });

    // Center and scale the model
    useEffect(() => {
        if (scene && !hasError) {
            // Clone the scene to avoid modifying the cached version
            const clonedScene = scene.clone();

            // Compute bounding box to center the model
            const box = new THREE.Box3().setFromObject(clonedScene);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());

            // Center the model
            clonedScene.position.sub(center);

            // Scale to fit in a reasonable view
            const maxDim = Math.max(size.x, size.y, size.z);
            if (maxDim > 0) {
                const scale = 5 / maxDim;
                clonedScene.scale.setScalar(scale);
            }

            // Add to group
            if (groupRef.current) {
                // Clear existing children
                while (groupRef.current.children.length > 0) {
                    groupRef.current.remove(groupRef.current.children[0]);
                }
                groupRef.current.add(clonedScene);
            }

            onSuccess?.();
        }
    }, [scene, hasError, onSuccess]);

    if (hasError) return null;
    return <group ref={groupRef} />;
}

// Model component that delegates to appropriate loader
function Model({ url, onError, onSuccess }: ModelProps) {
    const fileType = getFileType(url);
    const loaderUsed = fileType === 'zip' ? 'ZIPModel' : fileType === 'ply' ? 'PLYModel' : 'GLBModel';

    // Log only once per URL change
    const lastLoggedUrl = useRef<string | null>(null);
    if (lastLoggedUrl.current !== url) {
        console.log('[Room3DViewer] Model component:', { fileType, loaderUsed });
        lastLoggedUrl.current = url;
    }

    if (fileType === 'zip') {
        return <ZIPModel url={url} onError={onError} onSuccess={onSuccess} />;
    }
    if (fileType === 'ply') {
        return <PLYModel url={url} onError={onError} onSuccess={onSuccess} />;
    }
    // Default to GLB loader
    return <GLBModel url={url} onError={onError} onSuccess={onSuccess} />;
}

// Loading spinner shown while model loads
function LoadingSpinner() {
    const meshRef = useRef<THREE.Mesh>(null);

    useFrame((_, delta) => {
        if (meshRef.current) {
            meshRef.current.rotation.y += delta * 2;
            meshRef.current.rotation.x += delta * 0.5;
        }
    });

    return (
        <mesh ref={meshRef}>
            <boxGeometry args={[0.5, 0.5, 0.5]} />
            <meshStandardMaterial color="#4ade80" wireframe />
        </mesh>
    );
}

const Room3DViewer: React.FC<Room3DViewerProps> = ({ modelUrl, onLoadError, onLoadSuccess }) => {
    const [hasError, setHasError] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const viewAngleRef = useRef(0);

    // Log on mount
    useEffect(() => {
        console.log('[Room3DViewer] Component mounted with URL:', modelUrl?.slice(0, 80));
    }, []);

    const handleError = useCallback(() => {
        console.error('[Room3DViewer] 3D model failed to load, falling back to 2D', { url: modelUrl?.slice(0, 80) });
        setHasError(true);
        setIsLoading(false);
        onLoadError?.();
    }, [onLoadError, modelUrl]);

    const handleSuccess = useCallback(() => {
        console.log('[Room3DViewer] 3D model loaded successfully!', { url: modelUrl?.slice(0, 80) });
        setIsLoading(false);
        onLoadSuccess?.();
    }, [onLoadSuccess, modelUrl]);

    // Reset state when URL changes
    useEffect(() => {
        console.log('[Room3DViewer] URL changed, resetting state:', { newUrl: modelUrl?.slice(0, 80) });
        setHasError(false);
        setIsLoading(true);
    }, [modelUrl]);

    if (hasError) {
        console.log('[Room3DViewer] Rendering null due to error, parent will fall back to 2D');
        return null; // Parent will fall back to 2D image
    }

    return (
        <div className={`absolute inset-0 w-full h-full transition-opacity duration-300 ${isLoading ? 'opacity-0' : 'opacity-100'}`}>
            <Canvas
                gl={{
                    antialias: true,
                    alpha: true,
                    powerPreference: 'high-performance'
                }}
                style={{ background: 'transparent' }}
                scene={{ background: null }}
                onError={(e) => {
                    console.error('[Room3DViewer] Canvas error:', e);
                    handleError();
                }}
            >
                {/* Camera at origin - matches official Hunyuan viewer settings */}
                <PerspectiveCamera makeDefault position={[0, 0, 0]} fov={75} near={0.1} far={1000} />

                {/* Model with loading fallback - no lighting needed for MeshBasicMaterial */}
                <Suspense fallback={<LoadingSpinner />}>
                    <Model
                        url={modelUrl}
                        onError={handleError}
                        onSuccess={handleSuccess}
                    />
                </Suspense>

                {/* FPS-style controls - drag to look, WASD to move (like official viewer) */}
                <FPSControls onAngleChange={(angle) => { viewAngleRef.current = angle; }} />
            </Canvas>

            {/* View angle indicator - positioned below minimap, uses portal to escape z-index */}
            {!isLoading && typeof document !== 'undefined' && ReactDOM.createPortal(
                <ViewAngleIndicator angleRef={viewAngleRef} />,
                document.body
            )}


            {/* Hint overlay - same level as loader, shown after loaded */}
            {!isLoading && (
                <div className="absolute bottom-48 left-1/2 transform -translate-x-1/2
                                bg-black/30 backdrop-blur-sm text-white/50 text-xs px-3 py-1 rounded
                                pointer-events-none transition-opacity duration-500">
                    Drag to look around • WASD to move
                </div>
            )}
        </div>
    );
};

// Preload utility for caching models
export const preloadModel = (url: string) => {
    useGLTF.preload(url);
};

export default Room3DViewer;
