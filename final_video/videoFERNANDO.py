        "-framerate", str(fps), "-i", f"{workdir}/artists_anim_%04d.jpg",
        "-stream_loop", "-1", "-framerate", str(fps), "-t", str(loop_dur), "-i", f"{workdir}/artists_loop_%04d.jpg",
        "-framerate", str(fps), "-i", f"{workdir}/polaroid_anim_%04d.jpg",
        "-stream_loop", "-1", "-framerate", str(fps), "-t", str(loop_dur), "-i", f"{workdir}/polaroid_loop_%04d.jpg",
        "-framerate", str(fps), "-i", f"{workdir}/casa_anim_%04d.jpg",
        "-stream_loop", "-1", "-framerate", str(fps), "-t", str(loop_dur), "-i", f"{workdir}/casa_loop_%04d.jpg",
        "-stream_loop", "-1", "-i", cfg["music_path"]
    ]

    filter_parts = [
        # Ensamblaje Bloque 0 (fade-in pre-renderizado + frame estático repetido por ffmpeg)
        f"[0:v]format=yuv420p[b0_anim];[1:v]format=yuv420p[b0_loop];[b0_anim][b0_loop]concat=n=2:v=1:a=0,fps={fps}[blk0]",

        # Ensamblaje Bloque 1 (Split Simétrico 50/50)
        f"[3:v]format=yuv420p[l_anim];[4:v]format=yuv420p[l_loop];[l_anim][l_loop]concat=n=2:v=1:a=0[l_full]",
        f"[5:v]format=yuv420p[r_anim];[6:v]format=yuv420p[r_loop];[r_anim][r_loop]concat=n=2:v=1:a=0[r_full]",
        f"[l_full][r_full]hstack=inputs=2,fps={fps}[blk1]",
        
        # Ensamblaje Bloque 3 (Split Asimétrico Adaptativo)
        f"[7:v]format=yuv420p[p_anim];[8:v]format=yuv420p[p_loop];[p_anim][p_loop]concat=n=2:v=1:a=0[p_full]",
        f"[9:v]format=yuv420p[c_anim];[10:v]format=yuv420p[c_loop];[c_anim][c_loop]concat=n=2:v=1:a=0[c_full]",
        f"[p_full][c_full]hstack=inputs=2,fps={fps}[blk3]",
        
        # Formatear Bloque Estático/Pre-renderizado de fondo (Capa 3)
        f"[2:v]format=yuv420p,fps={fps}[blk2]",
        
        # Cadena de transiciones encadenadas xfade nativas en C
        f"[blk0][blk1]xfade=transition=fade:duration={trans}:offset={off1}[x1]",
        f"[x1][blk2]xfade=transition=fade:duration={trans}:offset={off2}[x2]",
        f"[x2][blk3]xfade=transition=fade:duration={trans}:offset={off3}[video]"
    ]
    
    cmd += [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[video]",
        "-map", "11:a",
        "-t", str(duracion_total),
        "-c:v", encoder, *encoder_flags,
        "-c:a", "aac", "-b:a", "128k",
        "-threads", str(cfg["threads"]),
        "-movflags", "+faststart",
        cfg["output_path"]
    ]

    os.makedirs(os.path.dirname(cfg["output_path"]), exist_ok=True)
    print("-> Mixing & Encoding final video via FFmpeg...")
    
    t_ff0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    t2 = time.time()

    if result.returncode != 0:
        print("FFMPEG CRITICAL ERROR:")
        print(result.stderr[-3000:])
        shutil.rmtree(workdir, ignore_errors=True)
        raise RuntimeError("ffmpeg execution failed")

    print(f"   FFmpeg completed in ({t2 - t_ff0:.2f}s)")
    print(f"✨ Rebuilt Done successfully in {t2 - t0:.2f}s total -> {cfg['output_path']}")
    shutil.rmtree(workdir, ignore_errors=True)
    return cfg["output_path"]

if __name__ == "__main__":
    generar_video(CONFIG)