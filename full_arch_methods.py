'''
Created on Feb 8, 2013

@author: Patrick
'''
import bpy
#from . 
import odcutils
import crown_methods
import time
import math
from mathutils import Vector, Matrix, Quaternion


#enums?
arch_types = ['MAX','MAND','LR','LL','LA','UR','UL','UA']
arch_enum = []
for index, arch in enumerate(arch_types):
    arch_enum.append((str(index), arch_types[index], str(index)))


#dictionaries and constants
quadrant_dict = {}
quadrant_dict['MAX'] = [str(i) for i in range(17,10,-1)] + [str(i) for i in range(21,28)]  #CW around the arch wrt z axis  pointing toard occlusals
quadrant_dict['MAND'] = [str(i) for i in range(47,40,-1)] + [str(i) for i in range(31,38)] #CCW around the arch wrt z axis  pointing toard occlusals
quadrant_dict['LR'] = [str(i) for i in range(41,48)]  #this list from midline -> distal
quadrant_dict['LL'] = [str(i) for i in range(31,38)]  #this list from midline -> distal
quadrant_dict['LA'] = ['43','42','41','31','32','33']  #notice this list is pt right to left
quadrant_dict['UR'] = [str(i) for i in range(11,18)]  #this list from midline -> distal
quadrant_dict['UL'] = [str(i) for i in range(21,28)]  #this list from midline -> distal
quadrant_dict['UA'] = ['13','12','11','21','22','23']  #notice this list is patient right to left



occ_direct_dict = {}

occ_direct_dict['MAX'] = -1 #CW
occ_direct_dict['MAND'] = 1  #CCW
occ_direct_dict['LR'] = -1 #CW
occ_direct_dict['LL'] = 1 
occ_direct_dict['LA'] = 1
occ_direct_dict['UR'] = 1 
occ_direct_dict['UL'] = -1 #CW
occ_direct_dict['UA'] = -1  #CW
#MD width in mm
max_teeth_width = [8.6,6.6,7.6,7.1,6.6,10.4,9.8]
man_teeth_width = [5.3,5.7,6.8,7,7.1,11.4,10.8]

#make a dictionary in case we access things out of order
size_dict = {}
for i in range(0,7):
    size_dict[str(11 + i)] = max_teeth_width[i]
    size_dict[str(21 + i)] = max_teeth_width[i]
    size_dict[str(31 + i)] = man_teeth_width[i]
    size_dict[str(41 + i)] = man_teeth_width[i]
    
#% distance from midline
max_norm_pos = [7.58,20.99,33.51,46.47,58.55,73.54,91.35]   
man_norm_pos = [4.9,15.06,26.62,39.37,52.40,69.50,90.02]
norm_dict = {}
for i in range(0,7):
    norm_dict[str(11 + i)] = max_norm_pos[i]
    norm_dict[str(21 + i)] = max_norm_pos[i]
    norm_dict[str(31 + i)] = man_norm_pos[i]
    norm_dict[str(41 + i)] = man_norm_pos[i]


def teeth_to_curve(context, arch, sextant, tooth_library, teeth = [], shift = 'BUCCAL', limit = False, link = False, reverse = False, mirror = False, debug = False, reorient = True):
    '''
    puts teeth along a curve for full arch planning
    args:
       curve - blender Curve object
       sextant - the quadrant or sextant that the curve corresponds to. enum in 'MAX', 'MAND', 'UR' 'LR' 'LR' 'LL' 'UA' 'LA' '
       teeth - list of odc_teeth, to link to or from.  eg, if tooth already
         a restoration it will use that object, if not, it will link a new
         blender object to that tooth as the restoration or contour.
       shift = whether to use buccal cusps, center of mass or, center of fossa to align onto cirve.  enum in 'BUCCAL', 'COM', 'FOSSA'
       limit - only link teeth for each tooth in teeth
       link - Bool, whether or not to link to/from the teeth list
    '''
    if debug:
        start = time.time()
        
    orig_arch_name = arch.name
    
    bpy.ops.object.select_all(action='DESELECT')
    context.scene.objects.active = arch
    arch.hide = False
    arch.select = True
    
    if mirror:
        #This should help with the mirroring?
        arch.data.resolution_u = 5 
        
        #if it doesn't have a mirror, we need to mirror it
        if "Mirror" not in arch.modifiers:
            bpy.ops.object.modifier_add(type='MIRROR')
        #non mirrored curve needed for appropriate constraining..
        #convert to mesh applies mirror, reconvert to curve gives us a full length curve
        arch.modifiers["Mirror"].merge_threshold = 5
        bpy.ops.object.convert(target='MESH',keep_original = True)
        bpy.ops.object.convert(target='CURVE', keep_original = False) #this will be the new full arch        
        arch = context.object
        arch.name = orig_arch_name + "_Mirrored"
    

    
    #we may want to switch the direction of the curve :-)
    #we may also want to handle this outside of this function
    if reverse:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.curve.switch_direction()
        bpy.ops.object.mode_set(mode='OBJECT')
        
    bpy.ops.object.convert(target='MESH', keep_original = True)
    arch_mesh = context.object #now the mesh conversion
    arch_len = 0
    mx = arch_mesh.matrix_world
    
    #do some calcs to the curve
    #TODO:  split this method off.  It may already
    #be in odcutils.
    occ_dir = Vector((0,0,0))  #this will end  be a normalized, global direction
    for i in range(0,len(arch_mesh.data.vertices)-1):
        v0 = arch_mesh.data.vertices[i]
        v1 = arch_mesh.data.vertices[i+1]
        V0 = mx*v1.co - mx*v0.co
        arch_len += V0.length
    
        if i < len(arch_mesh.data.vertices)-2:
            v2 = arch_mesh.data.vertices[i+2]
            V1 = mx*v2.co - mx*v1.co
            
            occ_dir += V0.cross(V1)
    
    if debug:
        print("arch is %f mm long" % arch_len)

    #pull values from the tooth size/data
        #if we are mirroring, we need to do some logic
    if mirror:
        if sextant not in ["UR","UL","LR","LL","MAX","MAND"]:
            print('Incorrect sextant for mirroring')
            return {'CANCELLED'}
        else:
            if sextant.startswith("U"):
                sextant = "MAX"
            elif sextant.startswith("L"):
                sextant = "MAND"
            #else..leave quadrant alone
            
    curve_teeth = quadrant_dict[sextant]
    occ_dir *= occ_direct_dict[sextant] * 1/(len(arch_mesh.data.vertices)-2)
    occ_dir.normalize()
    
    #this deletes the arch mesh...not the arch curve
    bpy.ops.object.delete()
    
    if reorient:
        arch_z = mx.to_quaternion() * Vector((0,0,1))
        arch_z.normalize()
        if math.pow(arch_z.dot(occ_dir),2) < .9:
            orient = odcutils.rot_between_vecs(Vector((0,0,1)), occ_dir) #align the local Z of bezier with occlusal direction (which is global).
            odcutils.reorient_object(arch, orient)
    if debug:
        print("working on these teeth %s" % ":".join(curve_teeth))
    
    #import/link teeth from the library
    restorations = []
    if link and len(context.scene.odc_teeth): 
        for tooth in context.scene.odc_teeth:
            if tooth.name[0:2] in curve_teeth:
                #TODO: restoration etc?
                #we will have to check later if we need to use the restoration
                #from this tooth
                restorations.append(tooth.name)
        if debug:               
            print("These restorations are already in the proposed quadrant %s" % ", ".join(restorations))
            
    
    #figure out which objects we are going to distribute.
    lib_teeth_names = odcutils.obj_list_from_lib(tooth_library) #TODO: check if tooth_library is valid?
    tooth_objects=[[None]]*len(curve_teeth) #we want this list to be mapped to curve_teeth with it's index...dictionary if we have to
    delete_later = []
    for i, planned_tooth in enumerate(curve_teeth):
        #this will be a one item list
        tooth_in_scene = [tooth for tooth in context.scene.odc_teeth if tooth.name.startswith(planned_tooth)]
        if link and len(tooth_in_scene):
            #check if the restoration is already there...if so, use it
            if tooth_in_scene[0].contour:
                tooth_objects[i] = bpy.data.objects[tooth_in_scene[0].contour]
        
            #if it's not there, add it in, and associate it with ODCTooth Object
            else:
                for tooth in lib_teeth_names:
                    if tooth.startswith(planned_tooth):  #necessary that the planned teeth have logical names
                        
                        new_name = tooth + "_ArchPlanned"
                        if new_name in bpy.data.objects:   
                            ob = bpy.data.objects[new_name]
                            me = ob.data
                            ob.user_clear()
                            bpy.data.objects.remove(ob)
                            bpy.data.meshes.remove(me)
                            context.scene.update()
                           
                        odcutils.obj_from_lib(tooth_library, tooth)
                        ob = bpy.data.objects[tooth]
                        context.scene.objects.link(ob)
                        ob.name = new_name
                        tooth_objects[i] = ob
                        tooth_in_scene[0].contour = ob.name
                        break #in case there are multiple copies?
        else: #the tooth is not existing restoration, and we want to put it in anyway
            for tooth in lib_teeth_names:
                if tooth.startswith(planned_tooth):
                    new_name = tooth + "_ArchPlanned"
                    if new_name in bpy.data.objects:   
                        ob = bpy.data.objects[new_name]
                        me = ob.data
                        ob.user_clear()
                        bpy.data.objects.remove(ob)
                        bpy.data.meshes.remove(me)
                        context.scene.update()
                        
                    odcutils.obj_from_lib(tooth_library, tooth)
                    ob = bpy.data.objects[tooth]
                    ob.name += "_ArchPlanned"
                    if limit:
                        context.scene.objects.link(ob)
                        delete_later.append(ob)    
                    else:
                        context.scene.objects.link(ob)
                        
                    tooth_objects[i]= ob
                    break  
    if debug:
        print(tooth_objects)
    
    #secretly, we imported the whole quadrant..we will delete them later
    teeth_len = 0
    lengths = [[0]] * len(curve_teeth) #list of tooth mesial/distal lengths
    locs = [[0]] * len(curve_teeth) #normalized list of locations
    for i, ob in enumerate(tooth_objects):
        lengths[i] = ob.dimensions[0]
        
        teeth_len += ob.dimensions[0]
        locs[i] = teeth_len - ob.dimensions[0]/2
    scale = arch_len/teeth_len
    crowding = teeth_len - arch_len
    
    if debug > 1:
        print(lengths)
        print(locs)
        print(scale)
        print("there is %d mm of crowding" % round(crowding,2))
        print("there is a %d pct archlength discrepancy" % round(100-scale*100, 2))
       
    #scale them to the right size
    for i, ob in enumerate(tooth_objects):
        
        if shift == 'FOSSA':
            delta = .05
        else:
            delta = 0
        #resize it
        ob.scale[0] *= scale + delta
        ob.scale[1] *= scale + delta
        ob.scale[2] *= scale + delta
        
    
        #find the location of interest we want?
        # bbox center, cusp tip? fossa/grove, incisal edge?
        #TODO:  odcutils.tooth_features(tooth,feature)  (world coords or local?)
        ob.location = Vector((0,0,0))
        if ob.rotation_mode != 'QUATERNION':
            ob.rotation_mode = 'QUATERNION'
        
        ob.rotation_quaternion = Quaternion((1,0,0,0))
            
        #center line...we want palatinal face median point z,y with midpointx and center line min local z
        #buccal line...we want incisal edge median local y, maxlocal z, midpoing bbox x and buccal cusp max z?

        context.scene.objects.active = ob
        ob.select = True
        ob.hide = False

        ob.constraints.new('FOLLOW_PATH')
        path_constraint = ob.constraints["Follow Path"]
        path_constraint.target = arch
        path_constraint.use_curve_follow = True
        #find out if we cross the midline
        if sextant in ['MAX','MAND','UA','LA']:
            path_constraint.forward_axis = 'FORWARD_X'
            if int(curve_teeth[i]) > 20 and int(curve_teeth[i]) < 40:
                path_constraint.forward_axis = 'TRACK_NEGATIVE_X'
        else:
            path_constraint.forward_axis = 'FORWARD_X'

        path_constraint.offset = 100*(-1 + locs[i]/teeth_len)


    #after arranging them on the curve, make a 2nd pass to spin them or not
    
    #decrease in number means mesial.  Except at midline.this will happen
    #we have constructed curve_teeth such that there will never be a non
    #integer change in adjacent list members. #eg, 
    #quaternion rotation rules
    # Qtotal = Qa * Qb represtnts rotation b followed by rotation a
    #what we are doing is testing the occlusal direction of one tooth vs the arch occlusal direction
    context.scene.update()
    ob_dist = tooth_objects[1]
    ob_mes = tooth_objects[0]
    mesial = int(curve_teeth[1]) - int(curve_teeth[0]) == 1 #if true....distal numbers > mesial numbers
    vect = ob_mes.matrix_world * ob_mes.location - ob_dist.matrix_world * ob_dist.location
    spin = (vect.dot(ob_dist.matrix_world.to_quaternion() * Vector((1,0,0))) < 0) == mesial

    tooth_occ = ob_mes.matrix_world.to_quaternion() * Vector((0,0,1))
    flip = tooth_occ.dot(occ_dir) > 0
        
    if debug:
        print('We will flip the teeth: %s. We will spin the teeth: %s.' % (str(flip), str(spin)))
    
    for ob in tooth_objects:
        if flip:
            ob.rotation_quaternion = Quaternion((0,1,0,0))
        if spin:
            ob.rotation_quaternion = Quaternion((0,0,0,1)) * ob.rotation_quaternion 
 
    for i, ob in enumerate(tooth_objects):
                    
            if shift == 'BUCCAL':
                groups = ["Incisal Edge", "Distobuccal Cusp","Mesiobuccal Cusp", "Buccal Cusp"]
                inds = []
                for vgroup in groups:
                    if vgroup in ob.vertex_groups:
                        inds += odcutils.vert_group_inds_get(context, ob, vgroup)
                max_z = 0
                max_ind = 0       
                for j in inds:
                    z = ob.data.vertices[j].co[2]
                    if z > max_z:
                        max_ind = j
                        max_z = z
                tip = ob.data.vertices[max_ind].co
                tooth_shift = Vector((0,tip[1]*ob.scale[1],tip[2]*ob.scale[2]))
                
                if sextant in ['MAX','MAND','UA','LA']: #no freakin idea why this is happening, but empirically, it's working
                    tooth_shift[1]*= -1
                    
                ob.location += (-1 + 2*flip) * tooth_shift
    
    
            if shift == 'FOSSA':
                groups = ["Middle Fissure", "Palatinal Face"]
                inds = []
                for vgroup in groups:
                    if vgroup in ob.vertex_groups and vgroup == "Middle Fissure":
                        inds += odcutils.vert_group_inds_get(context, ob, vgroup)
                
                        min_z = ob.dimensions[2]
                        min_ind = 0       
                        for j in inds:
                            z = ob.data.vertices[j].co[2]
                            if z < min_z:
                                min_ind = j
                                min_z = z
                                depth = ob.data.vertices[min_ind].co
                                tooth_shift = Vector((0,depth[1]*ob.scale[1],depth[2]*ob.scale[2]))
                                
                    elif vgroup in ob.vertex_groups and vgroup  == "Palatinal Face":
                        inds += odcutils.vert_group_inds_get(context, ob, vgroup)
                        mx =  Matrix.Identity(4)
                        com = odcutils.get_com(ob.data, inds, mx)
                        tooth_shift = odcutils.scale_vec_mult(com, ob.matrix_world.to_scale())
                
                if sextant in ['MAX','MAND','UA','LA']: #no freakin idea why this is happening, but empirically, it's working
                    tooth_shift[1]*= -1
                    
                ob.location += (-1 + 2*flip) * tooth_shift
    
    if limit:
        bpy.ops.object.select_all(action='DESELECT')        
        for ob in delete_later:
            ob.select = True
            
        context.scene.objects.active = ob
        bpy.ops.object.delete()        
    
def keep_arch_plan(context, curve, debug = False):
    '''
    context = bpy.context
    curve = Blender Curve Objectc
    '''
    
    for ob in bpy.data.objects:
        if len(ob.constraints):
            if 'Follow Path' in ob.constraints:
                if ob.constraints['Follow Path'].target == curve:
                    mx = ob.matrix_world.copy()
                    ob.constraints.remove(ob.constraints['Follow Path'])
                    ob.matrix_world = mx
                    ob.update_tag()
                    
    context.scene.update()
    
        
def cloth_fill_main(context, loop_obj, oct, smooth, debug = False):
    '''
    notes:
       make sure the user view is such that you can see the entire ring with
       out any corosses (knots)
       
       if calling from script not in 3dview, you can override the view
       
    args:
        context - blender context
        loop_obj:  blender curve object or mesh object representing just a loop
        oct - octree depth for the grid to fill.
        smooth - iteartions to smooth the surface (soap bubble effect)
    return:
        CurveMesh :  The filled looop object type Blender Object (Mesh) 
    '''
    
    #selection mode = verts
    sce = context.scene
    context.tool_settings.mesh_select_mode = [True,False,False]
    
    #get the space data
    v3d = bpy.context.space_data
    v3d.transform_orientation = 'GLOBAL'
    v3d.pivot_point = 'MEDIAN_POINT'
    
    region = v3d.region_3d        
    vrot = region.view_rotation #this is a quat
    
    #set object mode...force selection
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    
    bpy.ops.object.select_all(action='DESELECT')
    context.scene.objects.active = loop_obj
    loop_obj.select = True
    
    #change the mesh orientation to align with view..for blockout
    odcutils.reorient_object(loop_obj, vrot) #TODO test this
    sce.update()
        
    if loop_obj.type in {'CURVE','MESH'}:
        if loop_obj.type == 'CURVE':
            #check if cyclic
            if not loop_obj.data.splines[0].use_cyclic_u:
                loop_obj.data.splines[0].use_cyclic_u = True #TODO: add this over to margin

            #convert the curve to a mesh...so we can use it.
            bpy.ops.object.duplicate()
            bpy.ops.object.convert(target='MESH', keep_original = False)
            #active object is now the mesh version of the curve
            
        else:
            #make sure it's a loop
            if len(loop_obj.data.vertices) != len(loop_obj.data.edges):
                print('this is not a loop')
                return
            else:
                bpy.ops.object.duplicate()
                #active object is now the mesh duplicate
    
    #this will become our final cloth filled object
    CurveMesh = context.object
    CurveMesh.name = "Cloth Tray Mesh"
    
    #do some size estimation
    size = max(list(CurveMesh.dimensions))
    grid_predict = size * 0.9 / pow(oct,2)
    print("grid prediction is:  " + str(grid_predict))
     
                    
    #make a duplicate...
    current_objects = list(bpy.data.objects) #remember current objects to ID new ones later
    bpy.ops.object.duplicate()
    for obj in sce.objects:
        if obj not in current_objects:
            obj.name = "cloth_temp"
            Temp = obj
    
    #fill the the surface of the temp
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')       
    bpy.ops.mesh.fill()
    
    #stretch it out a little
    bpy.ops.mesh.select_all(action = 'DESELECT')
    bpy.context.tool_settings.mesh_select_mode = [False,True,False]
    bpy.ops.mesh.select_non_manifold()
    bpy.ops.object.editmode_toggle()
    
    eds = [ed for ed in Temp.data.edges if ed.select]
    barrier = .05 * min(Temp.dimensions)
    odcutils.extrude_edges_out_view(Temp.data, eds, Temp.matrix_world, barrier/5, debug = debug)
    bpy.ops.object.editmode_toggle()
    
    bpy.context.tool_settings.mesh_select_mode = [False,True,False]
    bpy.ops.mesh.select_non_manifold()
    bpy.ops.mesh.extrude_edges_move()
    bpy.ops.object.editmode_toggle()
    
    eds = [ed for ed in Temp.data.edges if ed.select]
    odcutils.extrude_edges_out_view(Temp.data, eds, Temp.matrix_world, barrier, debug = debug)
    bpy.ops.object.editmode_toggle()
    bpy.context.tool_settings.mesh_select_mode = [True,False,False]
    
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    
    CurveMesh.select = True
    sce.objects.active = CurveMesh
    CurveMesh.rotation_mode = 'QUATERNION'
    
    #make the origin the same as the bez curve?
    sce.cursor_location = loop_obj.location
    bpy.ops.object.origin_set(type = 'ORIGIN_CURSOR')
    
    if CurveMesh.parent:
        Parent = CurveMesh.parent
        reparent = True
        wmx = CurveMesh.matrix_world.copy()
        CurveMesh.parent = None
        CurveMesh.matrix_world = wmx
    else:
        wmx = Matrix.Identity(4)
        reparent = False
    #unrotate it so we can make a nice remesh surface
    #although why this doesn't work with local coords I dunno
    bpy.ops.object.rotation_clear()

    
    #flatten to view...fill in the loop
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    #get the space data
    v3d = bpy.context.space_data
    v3d.transform_orientation = 'LOCAL'
    v3d.pivot_point = 'MEDIAN_POINT'
    bpy.ops.transform.resize(value=(1, 1, 0), constraint_orientation='LOCAL')
    bpy.ops.mesh.looptools_space()
    bpy.ops.mesh.fill()

    #add modifiers
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.modifier_add(type='SOLIDIFY')
    bpy.ops.object.modifier_add(type='REMESH')
    
    solmod = CurveMesh.modifiers["Solidify"]
    solmod.thickness = grid_predict * .75
    
    remod = CurveMesh.modifiers["Remesh"]
    remod.octree_depth = oct
    remod.scale = .9
    
    #for some reason the modifier weren't updating
    bpy.ops.object.editmode_toggle()
    bpy.ops.object.editmode_toggle()
    

    #problem with applying modifiers...new method.
    mesh = CurveMesh.to_mesh(bpy.context.scene, True, 'RENDER')
    new_obj = bpy.data.objects.new(CurveMesh.name, mesh)
    bpy.context.scene.objects.link(new_obj)
    new_obj.matrix_world = wmx
    
    bpy.context.scene.objects.active = new_obj
    
    CurveMesh.select = True
    bpy.context.scene.objects.active = CurveMesh
    bpy.ops.object.delete()
    
    new_obj.select = True
    CurveMesh = new_obj
    bpy.context.scene.objects.active = CurveMesh
    '''
    bpy.ops.object.modifier_apply(modifier="Solidify")
    
    bpy.ops.object.editmode_toggle()
    bpy.ops.object.editmode_toggle()
    
    bpy.ops.object.modifier_apply(modifier="Remesh")
    '''

    
    bpy.ops.object.mode_set(mode='EDIT')        
    bpy.ops.mesh.select_all(action = 'DESELECT')
    bpy.ops.object.mode_set(mode = 'OBJECT')
    
    #make it a 2d obejct
    bpy.context.tool_settings.mesh_select_mode = [False,False,True]
    flat = False
    n = 0
    while not flat:
        
        #hope to select a polygon not on the border
        CurveMesh.data.polygons[n].select = True
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.mesh.faces_select_linked_flat()
        bpy.ops.object.mode_set(mode = 'OBJECT')
        
        sel_faces = [poly for poly in CurveMesh.data.polygons if poly.select]
        if len(sel_faces) > len(CurveMesh.data.polygons)/3:
            flat = True
        
        if n > 100:
            break
        n+= 1
    bpy.ops.object.mode_set(mode='EDIT')       
    bpy.ops.mesh.delete()
    bpy.context.tool_settings.mesh_select_mode = [False,True,False]
    bpy.ops.mesh.select_loose()
    bpy.ops.mesh.delete(type='EDGE')
    bpy.ops.mesh.select_non_manifold()
    bpy.context.tool_settings.mesh_select_mode = [True,False,False]
    bpy.ops.mesh.select_all(action='INVERT')
    bpy.ops.mesh.vertices_smooth(repeat = smooth)         
    
    bpy.ops.object.mode_set(mode='OBJECT')
    

    bpy.ops.object.modifier_add(type='SHRINKWRAP')
    swrap = CurveMesh.modifiers["Shrinkwrap"]
    swrap.wrap_method = 'PROJECT'
    swrap.use_project_z = True
    swrap.use_negative_direction = True
    swrap.use_positive_direction = True
    swrap.target = Temp
    
    CurveMesh.rotation_quaternion = vrot
    bpy.ops.object.modifier_apply(modifier="Shrinkwrap")
    
    
    if reparent:
        CurveMesh.update_tag()
        sce.update()
        odcutils.parent_in_place(CurveMesh, Parent)
        
    
    bpy.ops.object.select_all(action='DESELECT')

    if debug < 3:
        Temp.select = True
        sce.objects.active=Temp
        bpy.ops.object.delete()

    CurveMesh.select = True
    sce.objects.active = CurveMesh
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    
    bpy.context.tool_settings.mesh_select_mode = [False,True,False]
    bpy.ops.mesh.select_loose()
    bpy.ops.mesh.delete(type='EDGE')
    bpy.context.tool_settings.mesh_select_mode = [True,False,False]
    bpy.ops.object.mode_set(mode='OBJECT')
    
    mx = CurveMesh.matrix_world
    sum_edges = 0
    if len(CurveMesh.data.edges) != 0:
        for ed in CurveMesh.data.edges:
            v0 = CurveMesh.data.vertices[ed.vertices[0]]
            v1 = CurveMesh.data.vertices[ed.vertices[1]]
            V = mx*v1.co - mx*v0.co
            sum_edges += V.length
            
        avg_edge = sum_edges/len(CurveMesh.data.edges)
            
        if debug:
            print("average grid size: " + str(avg_edge))
        
    return CurveMesh
    
def link_selection_to_splint(context, odc_splint,clear = False, debug = False):
    #TODO check univ vs intl system
    teeth = odcutils.tooth_selection(context)
    implants = odcutils.implant_selection(context)
    
    t_names = [tooth.name for tooth in teeth]
    i_names = [imp.name for imp in implants]
    t_names.sort()
    i_names.sort()
    
    if clear:
        if len(teeth):
            odc_splint.tooth_string = ":".join(t_names)
            odc_splint.implant_string =":".join(i_names)
    
    else:
        if len(teeth):
            t_existing = odc_splint.tooth_string.split(':')
            print(t_existing)
            final_teeth = list(set(t_existing) | set(t_names))
            final_teeth.sort()
            print(final_teeth)
            odc_splint.tooth_string = ":".join(final_teeth)
            
        if len(implants):
            i_existing = odc_splint.implant_string.split(':')
            print(i_existing)
            final_imps = list(set(i_existing) | set(i_names))
            final_imps.sort()
            odc_splint.implant_string = ":".join(final_imps)
            print(final_imps)  

      
def splint_bezier_step_1(context, model, margin, axis, thickness, debug=False):
    '''
    notes:
       dependent on looptools relax
    args:
        model - blender mesh object
        margin - blender bezier object (closed)
        axis - vector representing the insertion axis. type Mathutils Vector
        thickness - float representing splint thickness in mm
    '''
    #tool settings
    context.tool_settings.vertex_group_weight = 1
    
    #make a rough offset model to use as outer shell
    me = model.data.copy()
    Refractory_Model = bpy.data.objects.new('Refractory',me)
    context.scene.objects.link(Refractory_Model)
    Refractory_Model.matrix_world = model.matrix_world
    mod = Refractory_Model.modifiers.new('Offset','SHRINKWRAP')
    mod.target = model
    mod.offset = 1.2 * thickness
    mod.use_keep_above_surface = True
    context.scene.update()
    
    #make a flat mesh in the outline
    Splint = cloth_fill_main(context, margin, 6, smooth = 10, debug = debug)
    Splint.name = 'Splint'
    
    #stretch the edges out slightly
    context.scene.objects.active = Splint
    bpy.ops.object.mode_set(mode='EDIT')
    context.tool_settings.mesh_select_mode = [False,True,False]
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()
    bpy.ops.mesh.extrude_edges_move()
    bpy.ops.mesh.looptools_relax(iterations = '10')
    bpy.ops.object.mode_set(mode='OBJECT')
    eds = [ed for ed in Splint.data.edges if ed.select]
    odcutils.extrude_edges_in(Splint.data, eds, Splint.matrix_world, axis, -1 * thickness, debug = debug)

    #make a copy to catch verts from falling
    falloff_data = Splint.data.copy()
    Falloff = bpy.data.objects.new('Falloff', falloff_data)
    context.scene.objects.link(Falloff)
    context.scene.objects.active = Falloff
    Falloff.matrix_world = Splint.matrix_world
    Falloff.select = True
    bpy.ops.object.mode_set(mode = 'EDIT')
    bpy.ops.mesh.extrude_edges_move()
    bpy.ops.mesh.looptools_relax(iterations = '10')
    bpy.ops.object.mode_set(mode='OBJECT')
    eds = [ed for ed in Falloff.data.edges if ed.select]
    odcutils.extrude_edges_in(Falloff.data, eds, Falloff.matrix_world, axis, -.5 * thickness, debug = debug)
    Falloff.select = False
    
    #group the mesh into appriate parts
    Splint.vertex_groups.new('Top')
    Splint.vertex_groups.new('Bottom')
    Splint.vertex_groups.new('Rim')
    Splint.vertex_groups.new('Bone')
    Splint.select = True
    context.scene.objects.active = Splint
    
    #go in, solidify it and make vertex groups meaningful
    bpy.ops.object.mode_set(mode = 'EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()
    bpy.ops.object.vertex_group_set_active(group = 'Rim')
    bpy.ops.object.vertex_group_assign()
    
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.extrude_region_move()
    bpy.ops.object.vertex_group_set_active(group = 'Top')
    bpy.ops.object.vertex_group_assign()
    
    bpy.ops.object.mode_set(mode='OBJECT')
    for v in Splint.data.vertices:
        if v.select:
            v.co += Vector((0,0,0.5))
    bpy.ops.object.mode_set(mode='EDIT')
    
    context.tool_settings.mesh_select_mode = [True,False,False]
    bpy.ops.mesh.select_all(action='INVERT')
    bpy.ops.object.vertex_group_set_active(group ='Bottom')
    bpy.ops.object.vertex_group_assign()
    
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.shade_smooth()
    
    #lift it high enough that it can project down
    #w/o worry of catching itself on udercuts
    
    trans = 10 * axis
    Splint.matrix_world[0][3] += trans[0]
    Splint.matrix_world[1][3] += trans[1]
    Splint.matrix_world[2][3] += trans[2]
    
    trans2 = -0.5 * axis
    Falloff.matrix_world[0][3] += trans2[0]
    Falloff.matrix_world[1][3] += trans2[1]
    Falloff.matrix_world[2][3] += trans2[2]
    
    mod = Splint.modifiers.new('Bpro1','SHRINKWRAP')
    mod.wrap_method = 'PROJECT'
    mod.use_project_z = True
    mod.use_negative_direction = True
    mod.use_positive_direction = False
    mod.offset = 3*thickness
    mod.vertex_group = 'Bottom'
    mod.auxiliary_target = Falloff
    mod.target = model
    
    mod = Splint.modifiers.new('Tpro1','SHRINKWRAP')
    mod.wrap_method = 'PROJECT'
    mod.use_project_z = True
    mod.use_negative_direction = True
    mod.use_positive_direction = False
    mod.offset = .5*thickness
    mod.vertex_group = 'Top'
    mod.auxiliary_target = Falloff
    mod.target = Refractory_Model
    
    mod = Splint.modifiers.new('Multires','MULTIRES')
    bpy.ops.object.multires_subdivide(modifier = 'Multires')
    bpy.ops.object.multires_subdivide(modifier = 'Multires')
    
    
    mod = Splint.modifiers.new('Bpro2','SHRINKWRAP')
    mod.wrap_method = 'PROJECT'
    mod.use_project_z = True
    mod.use_negative_direction = True
    mod.use_positive_direction = False
    mod.offset = .2*thickness
    mod.vertex_group = 'Bottom'
    mod.auxiliary_target = Falloff
    mod.target = model
    

    mod = Splint.modifiers.new('Bone','SHRINKWRAP')
    mod.wrap_method = 'PROJECT'
    mod.use_project_z = True
    mod.use_negative_direction = True
    mod.use_positive_direction = False
    mod.vertex_group = 'Bone'
    mod.project_limit = 4

    
    '''
    mod = Splint.modifiers.new('Tpro2','SHRINKWRAP')
    mod.wrap_method = 'PROJECT'
    mod.use_project_z = True
    mod.use_negative_direction = True
    mod.use_positive_direction = False
    mod.offset = 0
    mod.vertex_group = 'Top'
    mod.auxiliary_target = Falloff
    mod.target = Refractory_Model
    '''
    
    mod = Splint.modifiers.new('Smoot Edge','SMOOTH')
    mod.vertex_group = 'Rim'
    mod.iterations = 20
    mod.factor = 1

    Falloff.hide = True
    Refractory_Model.hide = True
    
    return Splint, Falloff, Refractory_Model


def add_tooth_boolean_splint(context, odc_tooth, odc_splint):
    
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action = 'DESELECT')
    
    if odc_splint.cut and odc_splint.cut in bpy.data.objects:
        Cut = bpy.data.objects[odc_splint.cut]
        Splint = bpy.data.objects[odc_splint.splint]
    else:
        if odc_splint.splint and odc_splint.splint in bpy.data.objects:
            Splint = bpy.data.objects[odc_splint.splint]
            context.scene.objects.active = Splint
            Splint.select = True
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.vertex_group_set_active(group='Bottom')
            bpy.ops.object.vertex_group_select()
            bpy.ops.mesh.duplicate(mode=1)
            bpy.ops.mesh.separate(type='SELECTED')
            bpy.ops.object.mode_set(mode='OBJECT')
            
            Cut = [ob for ob in context.selected_editable_objects if ob.name != Splint.name][0]
            
            Cut.modifiers['Multires'].levels = 1
            Cut.modifiers['Bpro2'].offset = 0.5
            
            for mod in Cut.modifiers:
                bpy.ops.object.modifier_apply(modifier = mod.name)
            
            odc_splint.cut = Cut.name
            Cut.select = False
            Splint.select = False
        
    if odc_tooth.contour and odc_tooth.contour in bpy.data.objects:
        bpy.ops.object.select_all(action='DESELECT')
        Contour = bpy.data.objects[odc_tooth.contour]
        Contour.select = True
        Contour.hide = False
        context.scene.objects.active = Contour
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.mesh.select_all(action = 'DESELECT')
        bpy.ops.mesh.select_non_manifold(extend= False)
        bpy.ops.mesh.duplicate(mode = 1)
        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT')
        Margin = [ob for ob in context.selected_editable_objects if ob.name != Contour.name][0]
        
        Margin.modifiers.remove(Margin.modifiers['Multires'])
        mod = Margin.modifiers.new('Shrinkwrap','SHRINKWRAP')
        mod.target = bpy.data.objects[odc_splint.cut]
        
        odc_tooth.margin = Margin.name
        crown_methods.seat_to_margin_improved(context, context.scene, odc_tooth, 3, debug = False)
        
        Contour.modifiers['Multires'].levels = 1
        mod = Contour.modifiers.new('Bool', 'BOOLEAN')
        mod.operation = 'INTERSECT'
        mod.object = Cut
        
        mod = Splint.modifiers.new('BOOL', 'BOOLEAN')
        mod.operation = 'UNION'
        mod.object = Contour
            