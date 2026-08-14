import { AmbientGradient } from './AmbientGradient'
import { ArchitecturalPipeline } from './ArchitecturalPipeline'

export function LandingBackground() {
  return (
    <div className="fixed inset-0 z-[-10] bg-[#FCFBF9]">
      <AmbientGradient />

      {/* 3D Focal Architectural Background */}
      <ArchitecturalPipeline />

      {/* Very Subtle Noise Texture Overlay to prevent gradient banding and add a paper-like feel */}
      <div className="absolute inset-0 bg-noise opacity-[0.015] mix-blend-multiply pointer-events-none z-10" />
    </div>
  )
}
