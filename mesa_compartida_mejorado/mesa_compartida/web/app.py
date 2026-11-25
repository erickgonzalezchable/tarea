"""Portal web local de Mesa Compartida; reutiliza las reglas de app.logica."""
import os
import sys
from functools import wraps
from pathlib import Path

# Permitir ejecutar 'python web/app.py' directamente desde cualquier directorio
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
except ModuleNotFoundError:
    print("\n[ERROR] Falta instalar Flask para el portal web.")
    print("Para iniciar el portal web ejecuta el script automático:")
    print("   ./iniciar_web.sh\n")
    print("O manualmente:")
    print("   python3 -m venv .venv")
    print("   source .venv/bin/activate")
    print("   pip install -r requirements-web.txt")
    print("   python -m web.app\n")
    sys.exit(1)

from app import db, logica as lg
from config import config as cfg
app=Flask(__name__)
app.secret_key=os.environ.get("MESA_SECRET_KEY") or "solo-desarrollo-cambiar-en-produccion"
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
@app.before_request
def init(): db.init_db(); lg.marcar_vencidas()
def user():
    return db.fetch_one("SELECT id,usuario,nombre,telefono,rol FROM usuarios WHERE id=? AND activo=1",(session.get("uid",-1),))
def login_required(fn):
    @wraps(fn)
    def w(*a,**k):
        if not user(): return redirect(url_for("login"))
        return fn(*a,**k)
    return w
def roles(*rs):
    def dec(fn):
        @wraps(fn)
        @login_required
        def w(*a,**k):
            if user()["rol"] not in rs: abort(403)
            return fn(*a,**k)
        return w
    return dec
@app.context_processor
def ctx(): return {"me":user(),"states":lg.ESTADOS,"foods":cfg.ALIMENTOS,"zones":cfg.ZONAS,"dining":cfg.COMEDORES}
@app.route("/")
def home(): return redirect(url_for("panel") if user() else url_for("login"))
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=lg.login(request.form.get("usuario",""),request.form.get("password",""))
        if u: session.clear(); session["uid"]=u["id"]; return redirect(url_for("panel"))
        flash("Usuario o contraseña incorrectos.","error")
    return render_template("login.html")
@app.route("/registro",methods=["GET","POST"])
def registro():
    """Alta de cuenta de donante (autoservicio). Los voluntarios los da de alta la coordinación."""
    if user(): return redirect(url_for("panel"))
    if request.method=="POST":
        try:
            lg.registrar_donante(request.form["usuario"],request.form["nombre"],request.form.get("telefono",""),request.form["password"])
            flash("Cuenta creada. Ya puedes iniciar sesión.","ok"); return redirect(url_for("login"))
        except Exception as e: flash(db.friendly_error(e),"error")
    return render_template("registro.html")
@app.post("/logout")
def logout(): session.clear(); return redirect(url_for("login"))
@app.get("/panel")
@login_required
def panel():
    u=user(); vs=[]; impact=None
    if u["rol"]=="ADMIN": ds=lg.todas_las_donaciones(); vs=lg.voluntarios_con_carga(); impact=lg.impacto()
    elif u["rol"]=="DONANTE": ds=lg.donaciones_de_donante(u["id"])
    else:
        v=lg.voluntario_de_usuario(u["id"]); ds=lg.donaciones_de_voluntario(v["id"]) if v else []
    return render_template("panel.html",ds=ds,vs=vs,impact=impact)
@app.route("/donacion/nueva",methods=["GET","POST"])
@roles("DONANTE","ADMIN")
def nueva():
    if request.method=="POST":
        try:
            uid=user()["id"] if user()["rol"]=="DONANTE" else int(request.form["donante_id"])
            did=lg.registrar_donacion(uid,request.form["alimento"],request.form["kg"],request.form["horas"],request.form["zona"],request.form["direccion"],request.form.get("observaciones",""),request.form["comedor"])
            flash(f"Donación #{did} registrada.","ok"); return redirect(url_for("panel"))
        except Exception as e: flash(db.friendly_error(e),"error")
    donors=db.fetch_all("SELECT id,nombre FROM usuarios WHERE rol='DONANTE' AND activo=1 ORDER BY nombre")
    return render_template("donacion.html",donors=donors)
@app.post("/donacion/<int:did>/assign")
@roles("ADMIN")
def assign(did):
    try: v=lg.asignar(did); flash("Asignada a "+v["nombre"]+" ("+v["placas"]+").","ok")
    except Exception as e: flash(str(e),"error")
    return redirect(url_for("panel"))
@app.post("/donacion/<int:did>/action")
@roles("VOLUNTARIO")
def action(did):
    v=lg.voluntario_de_usuario(user()["id"]); a=request.form.get("accion")
    try:
        if a=="iniciar": lg.iniciar(did,v["id"])
        elif a=="entregar": lg.marcar_entregada(did,v["id"])
        elif a=="incidente": lg.reportar_incidente(did,v["id"],request.form.get("tipo","Otro"),request.form.get("descripcion",""))
        else: raise lg.ReglaError("Acción no válida.")
        flash("Operación registrada.","ok")
    except Exception as e: flash(str(e),"error")
    return redirect(url_for("panel"))
@app.post("/donacion/<int:did>/cancel")
@roles("DONANTE","ADMIN")
def cancel(did):
    try:
        lg.cancelar(did,user()["id"] if user()["rol"]=="DONANTE" else None); flash("Donación cancelada.","ok")
    except Exception as e: flash(str(e),"error")
    return redirect(url_for("panel"))
@app.route("/voluntario/nuevo",methods=["GET","POST"])
@roles("ADMIN")
def volunteer():
    if request.method=="POST":
        try:
            lg.registrar_voluntario(request.form["usuario"],request.form["nombre"],request.form.get("telefono",""),request.form["password"],request.form["vehiculo"],request.form["placas"],request.form["capacidad"],bool(request.form.get("refrigerado")))
            flash("Voluntario registrado.","ok"); return redirect(url_for("panel"))
        except Exception as e: flash(db.friendly_error(e),"error")
    return render_template("voluntario.html")
@app.post("/voluntario/<int:vid>/estado")
@roles("ADMIN")
def volunteer_state(vid):
    try: lg.cambiar_estado_voluntario(vid,request.form["estado"]); flash("Estado actualizado.","ok")
    except Exception as e: flash(str(e),"error")
    return redirect(url_for("panel"))
@app.route("/password",methods=["GET","POST"])
@login_required
def password():
    if request.method=="POST":
        try: lg.cambiar_password(user()["id"],request.form["actual"],request.form["nueva"]); flash("Contraseña actualizada.","ok"); return redirect(url_for("panel"))
        except Exception as e: flash(str(e),"error")
    return render_template("password.html")
@app.errorhandler(403)
def forbidden(e): return render_template("error.html",code=403,msg="No tienes permisos para esta función."),403
@app.errorhandler(404)
def missing(e): return render_template("error.html",code=404,msg="No se encontró la página."),404
if __name__=="__main__":
    db.init_db(); app.run(host=os.environ.get("MESA_HOST","127.0.0.1"),port=int(os.environ.get("MESA_PORT","5000")),debug=False)
